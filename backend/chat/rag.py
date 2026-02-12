import json
import uuid
from typing import List
# from langchain_openai import ChatOpenAI
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List
from fastapi.responses import (
    StreamingResponse,
)
import re
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX
from langchain.messages import HumanMessage, SystemMessage, AIMessage
from vectorstore.retreiver import build_rag_messages, vector_store
from chat.think_filter import ThinkBlockFilter

# --- Monkey-patch MLXPipeline._call to fix formatter incompatibility ---
# langchain-community 0.4.1 passes `formatter` to mlx_lm.generate(),
# but mlx-lm 0.28.3 forwards **kwargs to generate_step() which doesn't
# accept it. Strip `formatter` before calling generate().
_original_call = MLXPipeline._call

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
    logits_processors = make_logits_processors(
        None, repetition_penalty, repetition_context_size
    )

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

def _patched_stream(self, prompt, stop=None, run_manager=None, **kwargs):
    import mlx.core as mx
    from mlx_lm.generate import generate_step  # fixed: was mlx_lm.utils
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
    logits_processors = make_logits_processors(
        None, repetition_penalty, repetition_context_size
    )

    for (token, prob), n in zip(
        generate_step(
            prompt=prompt_tokens,
            model=self.model,
            sampler=sampler,
            logits_processors=logits_processors,
        ),
        range(max_new_tokens),
    ):
        text = None
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

def _patched_chat_stream(self, messages, stop=None, run_manager=None, **kwargs):
    import mlx.core as mx
    from mlx_lm.generate import generate_step  # fixed: was mlx_lm.utils
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
    logits_processors = make_logits_processors(
        None, repetition_penalty, repetition_context_size
    )

    for (token, prob), n in zip(
        generate_step(
            prompt_tokens,
            self.llm.model,
            sampler=sampler,
            logits_processors=logits_processors,
        ),
        range(max_new_tokens),
    ):
        text = None
        if not isinstance(token, int):
            text = self.tokenizer.decode(token.item())
        else:
            text = self.tokenizer.decode(token)

        if text:
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=text))
            if run_manager:
                run_manager.on_llm_new_token(text, chunk=chunk)
            yield chunk

        if token == eos_token_id or (stop is not None and text in stop):
            break

ChatMLX._stream = _patched_chat_stream
# --- End monkey-patch ---

llm = MLXPipeline.from_model_id(
    "Qwen/Qwen3-4B-MLX-4bit",
    pipeline_kwargs={"max_tokens": 1000, "temp": 0.1},
)

chat_model = ChatMLX(llm=llm)

router = APIRouter()


class Message(BaseModel):
    id: str
    role: str
    content: str


# https://fastapi.tiangolo.com/tutorial/schema-extra-example/
class ChatPayload(BaseModel):
    messages: List[Message]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"messages": [{"id": "0", "role": "user", "content": "Who are you?"}]}
            ]
        }
    }


# Endpoint for pedagogical purposes, prefer the /chat endpoint
@router.post("/api/chat")
async def stream(request: Request, payload: ChatPayload):
    messages = [
        {
            "id": message.id,
            "role": message.role,
            "content": message.content,
        }
        for message in payload.messages
    ]
    chat = chat_model
    return StreamingResponse(
        send_completion_events(messages, chat=chat),
        media_type="text/event-stream",
    )


async def send_completion_events(messages, chat):
    result = await chat.ainvoke(
        [
            {
                "role": "system",
                "content": "your role is to evaluate whether a user is asking a question related to the Every Student Succeeds Act (ESSA). If so, reword the question for clarity then return the reworded question.  Otherwise answer [NULL].",
            },
            messages[-1],
        ]
    )
    result.content = re.sub(r"<think>.*?</think>\s*", "", result.content, flags=re.DOTALL)

    print("=> reworded question: ", result.content)
  
    KG_Query = result.content

    if KG_Query != "[NULL]":
        rag_messages = await build_rag_messages(
            question=KG_Query,
            knowledge_index=vector_store,
        )
    else:
        rag_messages = messages  # fallback: pass user messages directly

    # Yield empty assistant message placeholder
    assistant_message_id = str(uuid.uuid4())
    yield f"data: {json.dumps({'type': 'new_message', 'message': {'id': assistant_message_id, 'role': 'assistant', 'content': ''}})}\n\n"

    # Single LLM call — stream via astream with think-block filtering
    think_filter = ThinkBlockFilter()
    try:
        async for chunk in chat.astream(rag_messages):
            raw = chunk.content
            # print("==> raw content: ", raw)
            if not raw:
                continue
            filtered = think_filter.feed(raw)
            print("==> filtered content: ", filtered)
            if filtered:
                yield f"data: {json.dumps({'type': 'llm_chunk', 'content': filtered})}\n\n"
        remaining = think_filter.flush()
        if remaining:
            yield f"data: {json.dumps({'type': 'llm_chunk', 'content': remaining})}\n\n"
    except Exception as e:
        print(f"[streaming error] {e}")
        yield f"data: {json.dumps({'type': 'llm_chunk', 'content': f'[Error: {e}]'})}\n\n"




