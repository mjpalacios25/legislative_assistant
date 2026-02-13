"""Stateful streaming filter that removes <think>...</think> blocks from LLM output."""

import re


class ThinkBlockFilter:
    """Strips ``<think>...</think>`` reasoning blocks from a token stream.

    Usage::

        f = ThinkBlockFilter()
        for chunk in stream:
            cleaned = f.feed(chunk)
            if cleaned:
                send(cleaned)
        remaining = f.flush()
        if remaining:
            send(remaining)
    """

    def __init__(self) -> None:
        self._inside_think = False
        self._buffer = ""

    def feed(self, chunk: str) -> str:
        """Process the next chunk and return any safe-to-emit text."""
        self._buffer += chunk
        return self._drain()
        # return "".join(self._buffer)

    def flush(self) -> str:
        """Flush remaining content at stream end.

        Any unclosed ``<think>`` block (including a partial opening tag) is
        discarded — we never want to surface reasoning text to the user.
        """
        if self._inside_think:
            # Unclosed think block: discard everything buffered
            self._buffer = ""
            self._inside_think = False
            return ""

        # Discard any trailing partial `<think` prefix that never completed
        text = self._trim_partial_open(self._buffer)
        self._buffer = ""
        return text

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _drain(self) -> str:
        """Emit as much safe text from ``_buffer`` as possible."""
        output_parts: list[str] = []

        while True:
            if self._inside_think:
                # Look for the closing tag
                close_idx = self._buffer.find("</think>")
                if close_idx == -1:
                    # Might have a partial closing tag at the tail — keep
                    # buffering until we can decide.
                    break
                # Discard everything up to and including </think> plus optional whitespace
                after_close = close_idx + len("</think>")
                # Strip leading whitespace after the closing tag
                while after_close < len(self._buffer) and self._buffer[after_close] in (" ", "\n", "\r", "\t"):
                    after_close += 1
                self._buffer = self._buffer[after_close:]
                self._inside_think = False
                continue

            # Not inside a think block — look for an opening tag
            open_idx = self._buffer.find("<think>")
            if open_idx != -1:
                # Emit everything before the tag
                output_parts.append(self._buffer[:open_idx])
                self._buffer = self._buffer[open_idx + len("<think>"):]
                self._inside_think = True
                continue

            # No complete <think> found — but the tail of the buffer might
            # be a partial "<thi…" that will complete in the next chunk.
            safe = self._trim_partial_open(self._buffer)
            # Keep the potentially-partial suffix in the buffer
            self._buffer = self._buffer[len(safe):]
            output_parts.append(safe)
            break

        return "".join(output_parts)

    @staticmethod
    def _trim_partial_open(text: str) -> str:
        """Return *text* minus any trailing prefix of ``<think>``."""
        tag = "<think>"
        # Check suffixes of decreasing length
        for length in range(min(len(tag) - 1, len(text)), 0, -1):
            if tag.startswith(text[-length:]):
                return text[:-length]
        return text
