"""Async access to the local chat model.

The chat model differs by accelerator. On Apple silicon it is ``ChatMLX``, which
implements LangChain's async API. On NVIDIA it is ``ChatHuggingFace`` wrapping a
``HuggingFacePipeline``, which is synchronous only: ``_agenerate`` raises
``NotImplementedError`` and ``_astream`` reaches for an ``async_client`` that
only exists on ``HuggingFaceEndpoint``.

This module is the single place that knows the difference. Routers call
``acomplete`` / ``astream_text`` and never touch the model's async API directly.
``llm.model.SUPPORTS_NATIVE_ASYNC`` records which branch built the model.

It is also where the prompt is rendered, so that reasoning can be switched off
-- see :func:`_render_prompt`.
"""

import asyncio
import functools
import threading
from typing import Any, AsyncIterator, Sequence

# One local model on one accelerator: concurrent generations would race for
# device memory, so generation is serialised regardless of which branch runs.
_GPU_SLOT = asyncio.Semaphore(1)

# Sentinel marking the end of the worker thread's output.
_DONE = object()

# LangChain's internal message type names -> chat-template roles.
_ROLE_MAP = {
    "human": "user",
    "ai": "assistant",
    "system": "system",
    "tool": "tool",
}


def _supports_native_async() -> bool:
    """Report whether the configured chat model implements LangChain's async API.

    Parameters:
        None.

    Returns:
        bool: True when ``ainvoke``/``astream`` can be awaited directly.

    Reads the flag set by the ``DeviceManager`` branch in ``llm.model``. The
    import is deferred to call time on purpose: importing ``llm.model`` loads
    the model weights, and modules such as ``vectorstore.retreiver`` import this
    one without necessarily wanting that cost.
    """

    from llm.model import SUPPORTS_NATIVE_ASYNC

    return SUPPORTS_NATIVE_ASYNC


def _to_chatml(message: Any) -> dict:
    """Normalise one message into a ``{"role", "content"}`` dict.

    Parameters:
        message (Any): Either a role/content dict (which may carry extra keys
            such as "id") or a LangChain ``BaseMessage``.

    Returns:
        dict: A dict with exactly the "role" and "content" keys.

    Dicts are narrowed to the two keys the chat template cares about. Message
    objects are converted by mapping LangChain's ``type`` ("human", "ai", ...)
    onto the role names the template expects.
    """

    if isinstance(message, dict):
        return {"role": message["role"], "content": message["content"]}

    message_type = getattr(message, "type", "human")
    return {
        "role": _ROLE_MAP.get(message_type, message_type),
        "content": message.content,
    }


def _render_prompt(chat, messages: Sequence) -> str | None:
    """Render messages through the model's chat template with reasoning off.

    Parameters:
        chat: The LangChain chat model wrapping a local pipeline.
        messages (Sequence): The messages to render.

    Returns:
        str | None: The prompt string, or None when this model's template does
        not support toggling reasoning (callers then fall back to the chat
        model's own rendering).

    This works around ``ChatHuggingFace._to_chat_prompt``, which calls
    ``apply_chat_template(..., add_generation_prompt=True)`` with no way to pass
    ``enable_thinking``. Qwen's template then ends the prompt with a bare
    *opening* ``<think>`` tag, so the model emits its reasoning with that
    opening tag absent from the generated text -- which is exactly why neither
    ThinkBlockFilter nor the ``<think>.*?</think>`` regex could strip it, and
    pages of deliberation reached the user. ``enable_thinking=False`` instead
    prefills a closed, empty ``<think></think>`` block, so the model answers
    directly.
    """

    tokenizer = getattr(chat, "tokenizer", None)
    if tokenizer is None or getattr(chat, "llm", None) is None:
        return None
    if not hasattr(tokenizer, "apply_chat_template"):
        return None

    try:
        return tokenizer.apply_chat_template(
            [_to_chatml(m) for m in messages],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except (TypeError, KeyError, AttributeError, ValueError):
        # Template does not accept enable_thinking, or the messages are not
        # shaped the way it expects. Fall back to the chat model's rendering.
        return None


def _generation_kwargs(chat, max_tokens: int | None) -> dict:
    """Build call kwargs that cap how many tokens a single call may generate.

    Parameters:
        chat: The LangChain chat model the kwargs will be passed to.
        max_tokens (int | None): The ceiling to apply, or None for no cap.

    Returns:
        dict: Kwargs to splat into the generation call, empty when uncapped.

    Both backends read generation settings from a ``pipeline_kwargs`` call
    kwarg, but name the limit differently: MLXPipeline uses ``max_tokens`` and
    HuggingFacePipeline uses ``max_new_tokens``. MLXPipeline also *replaces* its
    configured dict rather than merging, so the model's existing settings are
    copied in first to avoid silently dropping things like temperature.
    """

    if max_tokens is None:
        return {}

    existing = dict(getattr(getattr(chat, "llm", None), "pipeline_kwargs", None) or {})
    key = "max_tokens" if _supports_native_async() else "max_new_tokens"
    existing[key] = max_tokens
    return {"pipeline_kwargs": existing}


def extract_text(content: Any) -> str:
    """Flatten a LangChain message content value into plain text.

    Parameters:
        content (Any): Either a string, or a list of content blocks where each
            block is a string or a dict carrying a "text" key.

    Returns:
        str: The concatenated text.

    Message content is a plain string for most models, but newer LangChain
    versions may return a list of typed blocks. Strings are returned as-is;
    otherwise each block contributes either itself (if a string) or its "text"
    entry, and the pieces are joined.
    """

    if isinstance(content, str):
        return content
    return "".join(
        block if isinstance(block, str) else block.get("text", "")
        for block in content
    )


def _chunk_text(chunk: Any) -> str:
    """Extract text from one streamed chunk, whichever shape it has.

    Parameters:
        chunk (Any): A ``str`` (when streaming the raw pipeline) or a message
            chunk carrying ``.content`` (when streaming the chat model).

    Returns:
        str: The chunk's text.

    Raw LLM streams yield strings while chat-model streams yield message
    chunks, and both paths occur depending on whether the prompt was rendered
    here or by the chat model.
    """

    return chunk if isinstance(chunk, str) else extract_text(chunk.content)


def _target(chat, messages: Sequence):
    """Choose what to call and what to send it.

    Parameters:
        chat: The LangChain chat model.
        messages (Sequence): The messages for this call.

    Returns:
        tuple: ``(runnable, payload)`` -- either the underlying pipeline plus a
        prompt string rendered with reasoning disabled, or the chat model plus
        the original messages.

    Prefers the locally rendered prompt so ``enable_thinking=False`` applies;
    falls back to letting the chat model render, which is what happens for any
    model whose template does not support the flag.
    """

    prompt = _render_prompt(chat, messages)
    if prompt is not None:
        return chat.llm, prompt
    return chat, messages


async def acomplete(chat, messages: Sequence, max_tokens: int | None = None) -> str:
    """Generate a complete response without blocking the event loop.

    Parameters:
        chat: The LangChain chat model, normally ``llm.model.chat_model``.
        messages (Sequence): The messages to send, as LangChain message objects
            or role/content dicts.
        max_tokens (int | None): Optional ceiling on generated tokens, for short
            structured calls such as the query classifier.

    Returns:
        str: The generated text.

    Acquires the single generation slot, then dispatches on
    ``SUPPORTS_NATIVE_ASYNC``: models with a real async implementation are
    awaited directly, while synchronous ones are run via ``asyncio.to_thread``
    so the FastAPI event loop stays free to serve other requests.
    """

    kwargs = _generation_kwargs(chat, max_tokens)
    runnable, payload = _target(chat, messages)

    async with _GPU_SLOT:
        if _supports_native_async():
            result = await runnable.ainvoke(payload, **kwargs)
        else:
            result = await asyncio.to_thread(
                functools.partial(runnable.invoke, payload, **kwargs)
            )

    return result if isinstance(result, str) else extract_text(result.content)


async def astream_text(
    chat, messages: Sequence, max_tokens: int | None = None
) -> AsyncIterator[str]:
    """Stream a response as text chunks, on either accelerator.

    Parameters:
        chat: The LangChain chat model, normally ``llm.model.chat_model``.
        messages (Sequence): The messages to send, as LangChain message objects
            or role/content dicts.
        max_tokens (int | None): Optional ceiling on generated tokens.

    Yields:
        str: Non-empty text chunks, in generation order.

    Holds the generation slot for the whole stream. On a natively async model it
    simply forwards ``astream``. On a synchronous one it starts ``stream`` on a
    worker thread, which pushes each chunk onto an ``asyncio.Queue`` via
    ``loop.call_soon_threadsafe``; this coroutine drains that queue. The thread
    forwards any exception through the same queue so a failure surfaces to the
    caller instead of hanging it, and a sentinel marks the end so the consumer
    always terminates.
    """

    kwargs = _generation_kwargs(chat, max_tokens)
    runnable, payload = _target(chat, messages)

    async with _GPU_SLOT:
        if _supports_native_async():
            async for chunk in runnable.astream(payload, **kwargs):
                text = _chunk_text(chunk)
                if text:
                    yield text
            return

        loop = asyncio.get_running_loop()
        # Unbounded: chunks are single tokens, and a bounded put_nowait would
        # raise QueueFull whenever the producer outruns the consumer.
        queue: asyncio.Queue = asyncio.Queue()
        stop = threading.Event()

        def produce() -> None:
            """Drive the synchronous stream, forwarding chunks to the queue."""
            try:
                for chunk in runnable.stream(payload, **kwargs):
                    if stop.is_set():
                        break
                    loop.call_soon_threadsafe(queue.put_nowait, _chunk_text(chunk))
            except BaseException as exc:  # noqa: BLE001 - re-raised on the consumer
                loop.call_soon_threadsafe(queue.put_nowait, exc)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, _DONE)

        task = asyncio.create_task(asyncio.to_thread(produce))
        try:
            while True:
                item = await queue.get()
                if item is _DONE:
                    break
                if isinstance(item, BaseException):
                    raise item
                if item:
                    yield item
        finally:
            # If the client disconnected, FastAPI closes this generator. Without
            # the stop flag the worker would keep generating to max_new_tokens
            # while still holding _GPU_SLOT, stalling every later request for
            # minutes. Setting it makes the worker exit after one more chunk.
            stop.set()
            await task
