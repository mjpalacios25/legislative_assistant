import asyncio
import json
import re
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain.messages import HumanMessage, SystemMessage
from llm.model import chat_model
from vectorstore.retreiver import build_rag_messages, vector_store, answer_with_rag
from chat.think_filter import ThinkBlockFilter

router = APIRouter()


class Message(BaseModel):
    id: str
    role: str
    content: str


class ChatPayload(BaseModel):
    messages: List[Message]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"messages": [{"id": "0", "role": "user", "content": "Who are you?"}]}
            ]
        }
    }


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(
        block if isinstance(block, str) else block.get("text", "")
        for block in content
    )


@router.post("/api/chat")
async def stream(request: Request, payload: ChatPayload):
    if not payload.messages:
        raise HTTPException(status_code=422, detail="messages cannot be empty")

    messages = [
        {"id": m.id, "role": m.role, "content": m.content}
        for m in payload.messages
    ]
    return StreamingResponse(
        send_rag_completion_events(messages, chat=chat_model),
        media_type="text/event-stream",
    )


async def send_completion_events(messages, chat):
    try:
        result = await chat.ainvoke(
            [
                {
                    "role": "system",
                    "content": "your role is to evaluate whether a user is asking a question related to the Every Student Succeeds Act (ESSA). If so, reword the question for clarity then return the reworded question. Otherwise answer [NULL].",
                },
                messages[-1],
            ]
        )
        raw_content = _extract_text(result.content)
        KG_Query = re.sub(r"<think>.*?</think>\s*", "", raw_content, flags=re.DOTALL).strip()

        print("=> reworded question: ", KG_Query)

        if KG_Query.upper() != "[NULL]":
            rag_messages = await build_rag_messages(
                question=KG_Query,
                knowledge_index=vector_store,
            )
        else:
            rag_messages = messages

        assistant_message_id = str(uuid.uuid4())
        yield f"data: {json.dumps({'type': 'new_message', 'message': {'id': assistant_message_id, 'role': 'assistant', 'content': ''}})}\n\n"

        think_filter = ThinkBlockFilter()
        async for patch in chat.astream_log(rag_messages):
            for op in patch.ops:
                if op["op"] == "add" and op["path"] == "/streamed_output/-":
                    raw = op["value"] if isinstance(op["value"], str) else op["value"].content
                    filtered = think_filter.feed(raw)
                    if filtered:
                        yield f"data: {json.dumps({'type': 'llm_chunk', 'content': filtered})}\n\n"
        remaining = think_filter.flush()
        if remaining:
            yield f"data: {json.dumps({'type': 'llm_chunk', 'content': remaining})}\n\n"

    except Exception as e:
        print(f"Error in completion: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred processing your request.'})}\n\n"


async def send_rag_completion_events(messages, chat):
    try:
        result = await chat.ainvoke(
            [
                {
                    "role": "system",
                    "content": "your role is to evaluate whether a user is asking a question related to the Every Student Succeeds Act (ESSA). If so, reword the question for clarity then return the reworded question. Otherwise answer [NULL].",
                },
                messages[-1],
            ]
        )
        raw_content = _extract_text(result.content)
        KG_Query = re.sub(r"<think>.*?</think>\s*", "", raw_content, flags=re.DOTALL).strip()

        print("=> reworded question: ", KG_Query)

        if KG_Query.upper() == "[NULL]":
            async for event in send_completion_events(messages, chat):
                yield event
            return

        answer_text, relevant_docs = await answer_with_rag(
            question=KG_Query,
            llm=chat,
            knowledge_index=vector_store,
        )

        assistant_message_id = str(uuid.uuid4())
        yield f"data: {json.dumps({'type': 'new_message', 'message': {'id': assistant_message_id, 'role': 'assistant', 'content': ''}})}\n\n"

        words = answer_text.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == 0 else " " + word
            yield f"data: {json.dumps({'type': 'llm_chunk', 'content': chunk})}\n\n"
            await asyncio.sleep(0.03)

    except Exception as e:
        print(f"Error in RAG completion: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': 'An error occurred processing your request.'})}\n\n"
