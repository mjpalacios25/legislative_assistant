import json
import re
import traceback
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from llm.model import chat_model
from vectorstore.retreiver import build_rag_messages, vector_store
from chat.think_filter import ThinkBlockFilter
from services.llm_service import acomplete, astream_text

router = APIRouter()

CLASSIFIER_PROMPT = (
    "Decide whether the user's question relates to the Every Student Succeeds "
    "Act (ESSA). If it does, reply with the question restated clearly in one "
    "line. If it does not, reply with exactly [NULL].\n"
    "Reply with that single line and nothing else. Do not explain your "
    "reasoning, do not show your work, and do not add any preamble."
)

# The classifier only ever needs one short line. Without a ceiling this model
# writes hundreds of tokens of deliberation, which both delays the first byte
# by ~a minute and ends up embedded in the retrieval query.
CLASSIFIER_MAX_TOKENS = 64


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
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


async def _classify_query(messages, chat) -> str:
    """Ask the model to restate the user's question, or reject it as off-topic.

    Parameters:
        messages (list): The conversation so far; only the last entry is sent.
        chat: The LangChain chat model to query.

    Returns:
        str: The reworded question, or "[NULL]" if it is not ESSA-related.

    Sends the classifier system prompt plus the latest user message through
    ``acomplete`` so the call runs off the event loop, then strips any
    ``<think>`` reasoning block from the reply before returning it.
    """

    raw_content = await acomplete(
        chat,
        [
            {"role": "system", "content": CLASSIFIER_PROMPT},
            messages[-1],
        ],
        max_tokens=CLASSIFIER_MAX_TOKENS,
    )
    return re.sub(r"<think>.*?</think>\s*", "", raw_content, flags=re.DOTALL).strip()


def _new_message_event(message_id: str) -> str:
    """Build the SSE frame that opens an empty assistant message.

    Parameters:
        message_id (str): The id the client should attach subsequent chunks to.

    Returns:
        str: A ``data: {...}`` SSE frame of type "new_message".

    Sent before any generation starts so the UI can render its loading
    indicator immediately rather than sitting blank through the classifier call.
    """

    return (
        "data: "
        + json.dumps(
            {
                "type": "new_message",
                "message": {"id": message_id, "role": "assistant", "content": ""},
            }
        )
        + "\n\n"
    )


async def _stream_answer(chat, prompt_messages):
    """Stream a model response as SSE ``llm_chunk`` events.

    Parameters:
        chat: The LangChain chat model to stream from.
        prompt_messages (list): The messages to send to the model.

    Yields:
        str: Fully formed ``data: {...}`` SSE frames.

    Pipes each chunk from ``astream_text`` through ``ThinkBlockFilter`` to drop
    ``<think>`` reasoning, yielding only non-empty text. The filter is flushed
    at the end to release anything it was holding back. The caller is expected
    to have already sent the ``new_message`` frame these chunks append to.
    """

    think_filter = ThinkBlockFilter()
    async for chunk in astream_text(chat, prompt_messages):
        filtered = think_filter.feed(chunk)
        if filtered:
            yield f"data: {json.dumps({'type': 'llm_chunk', 'content': filtered})}\n\n"

    remaining = think_filter.flush()
    if remaining:
        yield f"data: {json.dumps({'type': 'llm_chunk', 'content': remaining})}\n\n"


def _error_event() -> str:
    """Build the generic SSE error frame sent to the client.

    Parameters:
        None.

    Returns:
        str: A ``data: {...}`` SSE frame of type "error".

    The detail stays server-side; the client only learns that the request
    failed.
    """

    return (
        "data: "
        + json.dumps(
            {
                "type": "error",
                "message": "An error occurred processing your request.",
            }
        )
        + "\n\n"
    )


async def send_rag_completion_events(messages, chat):
    """Answer an ESSA question from the knowledge graph, streaming the reply.

    Parameters:
        messages (list): The conversation so far.
        chat: The LangChain chat model to query.

    Yields:
        str: SSE frames for the assistant's reply, or an error frame.

    Classifies the question first. Off-topic questions ("[NULL]") are answered
    from the conversation alone. Otherwise it retrieves matching bill text via
    ``build_rag_messages`` and streams the grounded answer. Any exception is
    logged with a traceback and reported to the client as a generic error.
    """

    try:
        # Sent first so the client can render its loading indicator immediately,
        # instead of sitting blank while the classifier and retrieval run.
        yield _new_message_event(str(uuid.uuid4()))

        KG_Query = await _classify_query(messages, chat)
        print("=> reworded question: ", KG_Query)

        if KG_Query.upper() == "[NULL]":
            # Off topic: answer from the conversation alone, without a second
            # classifier call.
            async for event in _stream_answer(chat, messages):
                yield event
            return

        rag_messages = await build_rag_messages(
            question=KG_Query,
            knowledge_index=vector_store,
        )

        async for event in _stream_answer(chat, rag_messages):
            yield event

    except Exception as e:
        print(f"Error in RAG completion: {e}")
        traceback.print_exc()
        yield _error_event()
