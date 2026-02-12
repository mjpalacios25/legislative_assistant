"""Tests for ThinkBlockFilter."""

import pytest
from chat.think_filter import ThinkBlockFilter


class TestThinkBlockFilter:
    """Unit tests for the stateful streaming think-block filter."""

    def test_no_think_block(self):
        """Plain text passes through unchanged."""
        f = ThinkBlockFilter()
        assert f.feed("Hello world") == "Hello world"
        assert f.flush() == ""

    def test_complete_block_single_chunk(self):
        """A complete <think>...</think> block in one chunk is stripped."""
        f = ThinkBlockFilter()
        result = f.feed("<think>reasoning here</think>The answer is 42.")
        result += f.flush()
        assert result == "The answer is 42."

    def test_block_split_across_two_chunks(self):
        """Think block content split across two chunks is fully stripped."""
        f = ThinkBlockFilter()
        out = f.feed("<think>start of")
        out += f.feed(" reasoning</think>Real answer.")
        out += f.flush()
        assert out == "Real answer."

    def test_opening_tag_split_across_chunks(self):
        """Opening <think> tag split across chunk boundaries."""
        f = ThinkBlockFilter()
        out = f.feed("Hello <thi")
        out += f.feed("nk>hidden</think> visible")
        out += f.flush()
        assert out == "Hello visible"

    def test_closing_tag_split_across_chunks(self):
        """Closing </think> tag split across chunk boundaries."""
        f = ThinkBlockFilter()
        out = f.feed("<think>hidden</thi")
        out += f.feed("nk>visible")
        out += f.flush()
        assert out == "visible"

    def test_unclosed_block_at_stream_end(self):
        """An unclosed <think> block is discarded on flush."""
        f = ThinkBlockFilter()
        out = f.feed("Prefix <think>some reasoning that never ends")
        out += f.flush()
        assert out == "Prefix "

    def test_multiple_think_blocks(self):
        """Multiple think blocks in a single stream are all stripped."""
        f = ThinkBlockFilter()
        out = f.feed("<think>first</think>A")
        out += f.feed("<think>second</think>B")
        out += f.flush()
        assert out == "AB"

    def test_whitespace_after_closing_tag(self):
        """Whitespace immediately after </think> is also stripped."""
        f = ThinkBlockFilter()
        out = f.feed("<think>stuff</think>  \n Answer")
        out += f.flush()
        assert out == "Answer"

    def test_text_before_and_after(self):
        """Text before and after the think block is preserved."""
        f = ThinkBlockFilter()
        out = f.feed("Before <think>hidden</think>After")
        out += f.flush()
        assert out == "Before After"

    def test_empty_think_block(self):
        """An empty think block is stripped cleanly."""
        f = ThinkBlockFilter()
        out = f.feed("<think></think>Content")
        out += f.flush()
        assert out == "Content"

    def test_many_small_chunks(self):
        """Simulates token-by-token streaming."""
        f = ThinkBlockFilter()
        text = "<think>internal</think>Hello"
        out = ""
        for char in text:
            out += f.feed(char)
        out += f.flush()
        assert out == "Hello"

    def test_flush_with_no_input(self):
        """Flushing an unused filter returns empty string."""
        f = ThinkBlockFilter()
        assert f.flush() == ""

    def test_partial_open_tag_at_end_no_completion(self):
        """A partial '<thi' at stream end that never completes is discarded."""
        f = ThinkBlockFilter()
        out = f.feed("Hello <thi")
        out += f.flush()
        assert out == "Hello "
