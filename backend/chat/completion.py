import json
from typing import List
# from langchain_openai import ChatOpenAI
# from langchain_huggingface import ChatHuggingFace
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Any, List, Optional
from fastapi.responses import (
    StreamingResponse,
)
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX
from langchain.messages import HumanMessage



llm = MLXPipeline.from_model_id(
    "Qwen/Qwen3-4B-MLX-4bit",
    pipeline_kwargs={"max_tokens": 500, "temp": 0.1},
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


# Endpoint for pedagogical purposes, prefer the /chat endpoint"
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
    # chat = ChatOpenAI()
    chat = chat_model

    return StreamingResponse(
        send_completion_events(messages, chat=chat),
        media_type="text/event-stream",
    )


async def send_completion_events(messages, chat):
    async for patch in chat.astream_log(messages):
        for op in patch.ops:
            if op["op"] == "add" and op["path"] == "/streamed_output/-":
                content = (
                    op["value"] if isinstance(op["value"], str) else op["value"].content
                )  # output format is not stable depending on langchain subclass
                json_dict = {"type": "llm_chunk", "content": content}
                json_str = json.dumps(json_dict)
                yield f"data: {json_str}\n\n"

# async def send_completion_events(messages, chat):
#     async for patch in chat.astream_log(messages):
#         for op in patch.ops:
#             if op["op"] == "add" and op["path"] == "/streamed_output/-":
#                 content = (
#                     op["value"] if isinstance(op["value"], str) else op["value"].content
#                 )  # output format is not stable depending on langchain subclass
#                 json_dict = {"type": "llm_chunk", "content": content}
#                 json_str = json.dumps(json_dict)
#                 yield f"data: {json_str}\n\n"
