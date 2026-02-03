import json
from typing import List
# from langchain_openai import ChatOpenAI
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List
from fastapi.responses import (
    StreamingResponse,
)
import yaml

#use connection with NEO4j 

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


# Endpoint for pedagogical purposes, prefer the /chat endpoint
@router.post("/api/rag")
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
                "content": "Does the user needs information from IPCC reports? If yes answer which a search query. Otherwise answer [NULL].",
            },
            messages[-1],
        ]
    )
    #insert connection to the NEO4j instance

    

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
#     result = await chat.ainvoke(
#         [
#             {
#                 "role": "system",
#                 "content": "Does the user needs information from IPCC reports? If yes answer which a search query. Otherwise answer [NULL].",
#             },
#             messages[-1],
#         ]
#     )
#     IPCC_query = result.content
#     if IPCC_query != "[NULL]":
#         IPCC_extracts = await search_IPCC(IPCC_query)
#         messages.append(
#             {
#                 "role": "function",
#                 "name": "search_IPCC",
#                 "content": yaml.dump(IPCC_extracts),
#             }
#         )
#         json_dict = {"type": "IPCC_search", "content": IPCC_extracts}
#         json_str = json.dumps(json_dict)
#         yield f"data: {json_str}\n\n"  # could be used to populate the UI

#     async for patch in chat.astream_log(messages):
#         for op in patch.ops:
#             if op["op"] == "add" and op["path"] == "/streamed_output/-":
#                 content = (
#                     op["value"] if isinstance(op["value"], str) else op["value"].content
#                 )  # output format is not stable depending on langchain subclass
#                 json_dict = {"type": "llm_chunk", "content": content}
#                 json_str = json.dumps(json_dict)
#                 yield f"data: {json_str}\n\n"
