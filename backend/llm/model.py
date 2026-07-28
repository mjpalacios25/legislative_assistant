
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX


llm = MLXPipeline.from_model_id(
    "Qwen/Qwen3-4B-MLX-4bit",
    pipeline_kwargs={"max_tokens": 4096, "temp": 0.1},
)

chat_model = ChatMLX(llm=llm)
