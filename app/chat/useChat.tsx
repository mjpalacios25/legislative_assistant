import jsonpatch from "fast-json-patch";
import { LLMEventValueSchema, Message } from "@/app/llm/types";
import { useChatQuery as useChatAPIQuery } from "@/app/queries/useChatQuery";
import { ServerSentEvent, readTextStream } from "@/app/streaming/readTextStream";
import { useCallback, useEffect, useState } from "react";
import { UseChatQuery } from "../llm/types";

const defaultMessages: Message[] = [];

export interface Chat {
  input: string;
  isLoading: boolean;
  isError: boolean;
  messages: Message[];
  cancel: () => void;
  submit: () => void;
  reset: () => void;
  setInput: React.Dispatch<React.SetStateAction<string>>;
}

export function useChat({
  useChatQuery = useChatAPIQuery,
  tools = [],
  initMessages = defaultMessages,
  modelName,
}: {
  useChatQuery?: UseChatQuery;
  tools?: string[];
  initMessages?: Message[];
  modelName?: string;
} = {}): Chat {
  const [isReading, setIsReading] = useState(false);
  const [input, setInput] = useState<string>("");
  const [inputMessages, setInputMessages] = useState<Message[]>(initMessages);
  const [messages, setMessages] = useState<Message[]>(initMessages);
  const [error, setError] = useState<any>(null);

  const {
    data: reader,
    isLoading,
    isError,
  } = useChatQuery({ messages: inputMessages, tools, modelName });

  useEffect(() => {
    if (reader === undefined) return;
    setIsReading(true);
    readTextStream({
      reader,
      onEvent: (event: ServerSentEvent) => {
        const { field, value: rawValue } = event;
        console.log("event", event);
        if (field === "data") {
          const value = LLMEventValueSchema.parse(rawValue);
          if (value.type === "new_message") {
            setMessages((prev) => {
              return [...prev, value.message];
            });
          }
          if (value.type === "message_patch") {
            const { message_id, patch } = value;
            setMessages((prev) => {
              const targetIndex = prev.findIndex(({ id }) => id === message_id);
              if (targetIndex === -1) return prev;
              const targetMessage = structuredClone(prev[targetIndex]);
              const newMessage = jsonpatch.applyPatch(
                targetMessage,
                patch,
              ).newDocument;
              return [
                ...prev.slice(0, targetIndex),
                newMessage,
                ...prev.slice(targetIndex + 1),
              ];
            });
          }
          if (value.type === "llm_chunk") {
            setMessages((prev) => {
              const lastMessage = prev
                .filter(({ role }) => role === "assistant")
                .at(-1);
              if (!lastMessage) {
                return [
                  ...prev,
                  { id: crypto.randomUUID(), role: "assistant" as const, content: value.content },
                ];
              }
              const newContent = lastMessage.content + value.content;
              return [
                ...prev.slice(0, -1),
                { ...lastMessage, content: newContent },
              ];
            });
          }
        }
      },
    })
      .then(() => setIsReading(false))
      .catch((err: any) => {
        console.log("Error reading stream: ", err);
        setError(err);
        setIsReading(false);
      });

    return () => {
      if (reader) reader?.cancel();
    };
  }, [reader]);

  const reset = useCallback(() => {
    setInput("");
    if (reader) {
      reader?.cancel();
    }
    setInputMessages(initMessages);
    setMessages(initMessages);
  }, [initMessages, reader]);

  const cancel = useCallback(() => {
    if (reader) {
      reader?.cancel();
    }
  }, [reader]);

  const submit = useCallback(() => {
    setInput("");
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
    };
    setInputMessages((prev) => [...prev, userMessage]);
    setMessages((prev) => [...prev, userMessage]);
  }, [input]);

  return {
    messages,
    isLoading: isReading || isLoading,
    isError: !!error || isError,
    input,
    cancel,
    reset,
    setInput,
    submit,
  };
}
