import { expect, test } from 'vitest'
import { describe, it } from "vitest";
import { render, screen } from '@testing-library/react'
import { act } from "react-dom/test-utils";
import { useCompletion } from "../completion/useCompletion";
import { buildSSE, buildMockStream } from "../streaming/mock";
import { Message, UseChatQuery } from "../llm/types";

describe("useCompletion", () => {
  it("returns the completion", async () => {
    const { reader, controller } = buildMockStream();
    const query = setup({
      messages: [],
      useChatQuery: () => ({ isLoading: false, isError: false, data: reader }),
    });

    await act(async () => {
      controller.enqueue(
        buildSSE({
          field: "data",
          value: { type: "llm_chunk", content: "Hello World!" },
        }),
      );
    });

    expect(query?.data).toEqual("Hello World!");
    await act(() => controller.close());
  });
  it("returns reduced chunks", async () => {
    const { reader, controller } = buildMockStream();
    const query = setup({
      messages: [],
      useChatQuery: () => ({ isLoading: false, isError: false, data: reader }),
    });

    await act(async () => {
      controller.enqueue(
        buildSSE({
          field: "data",
          value: { type: "llm_chunk", content: "Hello" },
        }),
      );
      controller.enqueue(
        buildSSE({
          field: "data",
          value: { type: "llm_chunk", content: " World!" },
        }),
      );
    });

    expect(query?.data).toEqual("Hello World!");
    await act(() => controller.close());
  });
});

// https://kentcdodds.com/blog/how-to-test-custom-react-hooks
function setup({
  messages,
  useChatQuery,
}: {
  messages: Message[];
  useChatQuery: UseChatQuery;
}) {
  const returnVal = {} as any;
  function TestComponent() {
    const chat = useCompletion({ messages, useChatQuery });
    Object.assign(returnVal, chat);
    return null; // No need to render anything
  }
  render(<TestComponent />);
  return returnVal;
}
