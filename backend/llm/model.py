"""
Shared MLX LLM singleton with compatibility patches for mlx-lm 0.28.3 +
langchain-community 0.4.1. Import this module before any other code that
touches MLXPipeline or ChatMLX.
"""
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX


# --- Patch 1: MLXPipeline._call ---
# langchain-community 0.4.1 passes a `formatter` kwarg to mlx_lm.generate(),
# which mlx-lm 0.28.3 forwards to generate_step() — generate_step rejects it.
def _patched_call(self, prompt, stop=None, run_manager=None, **kwargs):
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_logits_processors, make_sampler

    pipeline_kwargs = kwargs.get("pipeline_kwargs", self.pipeline_kwargs) or {}
    temp = pipeline_kwargs.get("temp", 0.0)
    max_tokens = pipeline_kwargs.get("max_tokens", 100)
    verbose = pipeline_kwargs.get("verbose", False)
    repetition_penalty = pipeline_kwargs.get("repetition_penalty", None)
    repetition_context_size = pipeline_kwargs.get("repetition_context_size", None)
    top_p = pipeline_kwargs.get("top_p", 1.0)
    min_p = pipeline_kwargs.get("min_p", 0.0)
    min_tokens_to_keep = pipeline_kwargs.get("min_tokens_to_keep", 1)

    sampler = make_sampler(temp, top_p, min_p, min_tokens_to_keep)
    logits_processors = make_logits_processors(None, repetition_penalty, repetition_context_size)

    return generate(
        model=self.model,
        tokenizer=self.tokenizer,
        prompt=prompt,
        max_tokens=max_tokens,
        verbose=verbose,
        sampler=sampler,
        logits_processors=logits_processors,
    )


MLXPipeline._call = _patched_call


# --- Patch 2: MLXPipeline._stream ---
# generate_step moved from mlx_lm.utils to mlx_lm.generate in mlx-lm 0.28.3.
def _patched_stream(self, prompt, stop=None, run_manager=None, **kwargs):
    import mlx.core as mx
    from mlx_lm.generate import generate_step
    from mlx_lm.sample_utils import make_logits_processors, make_sampler
    from langchain_core.outputs import GenerationChunk

    pipeline_kwargs = kwargs.get("pipeline_kwargs", self.pipeline_kwargs) or {}
    temp = pipeline_kwargs.get("temp", 0.0)
    max_new_tokens = pipeline_kwargs.get("max_tokens", 100)
    repetition_penalty = pipeline_kwargs.get("repetition_penalty", None)
    repetition_context_size = pipeline_kwargs.get("repetition_context_size", None)
    top_p = pipeline_kwargs.get("top_p", 1.0)
    min_p = pipeline_kwargs.get("min_p", 0.0)
    min_tokens_to_keep = pipeline_kwargs.get("min_tokens_to_keep", 1)

    prompt = self.tokenizer.encode(prompt, return_tensors="np")
    prompt_tokens = mx.array(prompt[0])
    eos_token_id = self.tokenizer.eos_token_id
    detokenizer = self.tokenizer.detokenizer
    detokenizer.reset()

    sampler = make_sampler(temp or 0.0, top_p, min_p, min_tokens_to_keep)
    logits_processors = make_logits_processors(None, repetition_penalty, repetition_context_size)

    for (token, prob), n in zip(
        generate_step(
            prompt=prompt_tokens,
            model=self.model,
            sampler=sampler,
            logits_processors=logits_processors,
        ),
        range(max_new_tokens),
    ):
        detokenizer.add_token(token)
        detokenizer.finalize()
        text = detokenizer.last_segment
        if text:
            chunk = GenerationChunk(text=text)
            if run_manager:
                run_manager.on_llm_new_token(chunk.text)
            yield chunk
        if token == eos_token_id or (stop is not None and text in stop):
            break


MLXPipeline._stream = _patched_stream


# --- Patch 3: ChatMLX._stream ---
# chat.astream_log() calls ChatMLX._stream(), which also had the stale
# mlx_lm.utils import. Critical for streaming on the non-RAG path.
def _patched_chat_stream(self, messages, stop=None, run_manager=None, **kwargs):
    import mlx.core as mx
    from mlx_lm.generate import generate_step
    from mlx_lm.sample_utils import make_logits_processors, make_sampler
    from langchain_core.outputs import ChatGenerationChunk
    from langchain_core.messages import AIMessageChunk

    model_kwargs = kwargs.get("model_kwargs", self.llm.pipeline_kwargs) or {}
    temp = model_kwargs.get("temp", 0.0)
    max_new_tokens = model_kwargs.get("max_tokens", 100)
    repetition_penalty = model_kwargs.get("repetition_penalty", None)
    repetition_context_size = model_kwargs.get("repetition_context_size", None)
    top_p = model_kwargs.get("top_p", 1.0)
    min_p = model_kwargs.get("min_p", 0.0)
    min_tokens_to_keep = model_kwargs.get("min_tokens_to_keep", 1)

    llm_input = self._to_chat_prompt(messages, tokenize=True, return_tensors="np")
    prompt_tokens = mx.array(llm_input[0])
    eos_token_id = self.tokenizer.eos_token_id

    sampler = make_sampler(temp or 0.0, top_p, min_p, min_tokens_to_keep)
    logits_processors = make_logits_processors(None, repetition_penalty, repetition_context_size)

    for (token, prob), n in zip(
        generate_step(
            prompt_tokens,
            self.llm.model,
            sampler=sampler,
            logits_processors=logits_processors,
        ),
        range(max_new_tokens),
    ):
        text = self.tokenizer.decode(token.item() if not isinstance(token, int) else token)
        if text:
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=text))
            if run_manager:
                run_manager.on_llm_new_token(text, chunk=chunk)
            yield chunk
        if token == eos_token_id or (stop is not None and text in stop):
            break


ChatMLX._stream = _patched_chat_stream
# --- End patches ---

llm = MLXPipeline.from_model_id(
    "Qwen/Qwen3-4B-MLX-4bit",
    pipeline_kwargs={"max_tokens": 4096, "temp": 0.1},
)

chat_model = ChatMLX(llm=llm)
