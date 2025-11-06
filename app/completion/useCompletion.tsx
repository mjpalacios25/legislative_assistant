'use client';

import { useState, useEffect } from "react";
import { useChatQuery as useChatAPIQuery } from "@/app/queries/useChatQuery";
import { readTextStream, ServerSentEvent } from "@/app/streaming/readTextStream";
import {
  LLMEventValueSchema,
  Message,
  OpenAIChatCompletionChunkSchema,
  QueryResult,
  UseChatQuery,
} from "@/app/llm/types";

export function useCompletion({
  messages,
  useChatQuery = useChatAPIQuery,
}: {
  messages: Message[];
  useChatQuery?: UseChatQuery;
}): QueryResult<string> {
  const [isReading, setIsReading] = useState<boolean>(false);
  const [readingError, setReadingError] = useState<boolean>(false);
  const {
    data: reader,
    isLoading,
    isError,
  } = useChatQuery({ messages, endpoint: "/api/simple-chat" });
  const [completion, setCompletion] = useState<string>("");
  useEffect(() => {
    if (reader === undefined) return;
    setIsReading(true);
    setCompletion("");
    readTextStream({
      reader,
      onEvent: (event: ServerSentEvent) => {
        const { field, value: rawValue } = event;
        if (field === "data") {
          const OpenAIChunk =
            OpenAIChatCompletionChunkSchema.safeParse(rawValue);
          if (OpenAIChunk.success) {
            // Remark: we need to pass an function to avoid problems with React batching.
            // https://react.dev/learn/queueing-a-series-of-state-updates
            setCompletion(
              (prev) => prev + OpenAIChunk.data.choices[0].delta.content,
            );
          }
          const value = LLMEventValueSchema.parse(rawValue);
          if (value.type === "llm_chunk") {
            setCompletion((prev) => prev + value.content);
          }
        }
      },
    })
      .then(() => setIsReading(false))
      .catch((err: any) => {
        console.log("Error reading stream: ", err);
        setReadingError(err);
      });
  }, [reader]);
  return {
    data: isLoading ? "" : completion,
    isLoading: isReading || isLoading,
    isError: isError || !!readingError,
  };
}
