from sample.system_check import DeviceManager


device_manager = DeviceManager()

# Whether `chat_model` implements LangChain's async API natively. Set per
# branch below. Declared here first so the name always exists, even if no
# branch matches -- a CPU-only host should fail on the missing `chat_model`
# rather than on a more confusing NameError about this flag.
SUPPORTS_NATIVE_ASYNC = False

if device_manager.is_nvidia():
    ## Use the NVIDIA GPU for inference and download the model from Hugging Face Hub
    import torch
    from transformers import BitsAndBytesConfig
    from langchain_huggingface import HuggingFacePipeline, ChatHuggingFace

    # Qwen3.5-9B is 17.98 GiB at bf16, which does not fit in 16 GB of VRAM.
    # NF4 brings the weights to ~6 GiB and leaves the rest for KV cache.
    # (Qwen3.5-27B-GPTQ-Int4 is not an option here: its `dynamic` config leaves
    # attention/visual layers in bf16, so it is 28.15 GiB on disk.)
    quant_config = BitsAndBytesConfig(
        load_in_4bit = True,
        bnb_4bit_quant_type = "nf4",
        bnb_4bit_compute_dtype = torch.bfloat16,
        bnb_4bit_use_double_quant = True,
    )

    llm = HuggingFacePipeline.from_model_id(
        model_id = "Qwen/Qwen3.5-9B",
        task = "text-generation",
        # `device_map` belongs here rather than in model_kwargs, and `device`
        # must stay unset — from_model_id rejects being given both.
        device_map = "auto",
        model_kwargs = dict(
            quantization_config = quant_config,
            dtype = torch.bfloat16,
        ),
        pipeline_kwargs = dict(
            # KV cache, not weights, is the memory ceiling now. Raise if headroom allows.
            max_new_tokens = 4096,
            do_sample = True,
            temperature = 1.0,
            top_p = 0.95,
            top_k = 20,
            min_p = 0.0,
            # presence_penalty removed: vLLM/OpenAI-style, not a HF generate() kwarg.
            repetition_penalty = 1.0,
            return_full_text = False,
        )
    )

    chat_model = ChatHuggingFace(llm=llm)

    # ChatHuggingFace._agenerate raises NotImplementedError when the wrapped llm
    # is a HuggingFacePipeline, and _astream is unguarded -- it reaches for
    # `self.llm.async_client`, which only exists on HuggingFaceEndpoint. Callers
    # must go through the thread bridge in services/llm_service.py.
    SUPPORTS_NATIVE_ASYNC = False


elif device_manager.is_apple_silicon():
    ## Use the Apple Silicon GPU for inference and download the model from Hugging Face Hub

    from langchain_community.llms.mlx_pipeline import MLXPipeline
    from langchain_community.chat_models.mlx import ChatMLX


    llm = MLXPipeline.from_model_id(
        "Qwen/Qwen3-4B-MLX-4bit",
        pipeline_kwargs={"max_tokens": 4096, "temp": 0.1},
    )

    chat_model = ChatMLX(llm=llm)

    # ChatMLX does not override _astream, and its _agenerate delegates to
    # MLXPipeline, which inherits langchain-core's run_in_executor fallback.
    # ainvoke/astream therefore work directly.
    SUPPORTS_NATIVE_ASYNC = True


if __name__ == "__main__":
    # Test the chat model
    test_prompt = "Hello, how are you?"
    response = chat_model.invoke([{"role": "user", "content": test_prompt}])
    print("Response:", response)