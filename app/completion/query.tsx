'use client'
import { useMemo, useState } from "react";
import StreamedText from "../llm/StreamedText";
import { useCompletion } from "./useCompletion";
import { Message } from "../llm/types";

export default function Query({ text }: { text: string }) {
  const messages: Message[] = useMemo(() => {
    return [
      {
        id: crypto.randomUUID(),
        role: "system",
        content: "You are a legislative assistant",
      },
      { id: crypto.randomUUID(), role: "user", content: `${text}` },
    ];
  }, [text]);
  const { data, isLoading, isError } = useCompletion({ messages });
  if (isError) return <>Error!</>;
  return <StreamedText text={data ?? ""} isLoading={isLoading} />;
}