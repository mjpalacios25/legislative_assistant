import jsonpatch from "fast-json-patch";
import { LLMEventValueSchema, Message } from "@/app/llm/types";
import { fetchChat } from "@/app/queries/fetchChat";
import { ServerSentEvent, readTextStream } from "@/app/streaming/readTextStream";
import { useCallback, useEffect, useRef, useState } from "react";

const defaultMessages: Message[] = [];

export interface Chat {
  input: string;
  isLoading: boolean;
  isError: boolean;
  error: string | null;
  messages: Message[];
  cancel: () => void;
  submit: () => void;
  reset: () => void;
  setInput: React.Dispatch<React.SetStateAction<string>>;
}

/**
 * Drives one chat conversation against the streaming /api/chat endpoint.
 *
 * The stream is deliberately NOT held in a TanStack query. A
 * ReadableStreamDefaultReader can be drained exactly once, so caching it meant
 * any repeat of the same query key — a remount, a Fast Refresh, navigating
 * between / and /rag, or simply asking the same question twice — handed back an
 * already-consumed reader. The read loop then saw done:true immediately and
 * rendered nothing, with no error. Streaming is an action, so it is started
 * imperatively from submit() and owned by this hook.
 */
export function useChat({
  tools = [],
  initMessages = defaultMessages,
  modelName,
}: {
  tools?: string[];
  initMessages?: Message[];
  modelName?: string;
} = {}): Chat {
  const [isReading, setIsReading] = useState(false);
  const [input, setInput] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>(initMessages);
  const [error, setError] = useState<string | null>(null);

  const activeAssistantIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  // Read inside submit() so the request carries the latest conversation
  // without submit() having to change identity on every keystroke.
  const messagesRef = useRef<Message[]>(messages);
  messagesRef.current = messages;
  // Chat.tsx rebuilds this array every render, so hold it in a ref rather than
  // listing it as a dependency and re-creating submit() each time.
  const toolsRef = useRef<string[]>(tools);
  toolsRef.current = tools;

  // Abort any in-flight stream when the component goes away. Unlike the
  // previous effect this runs only on unmount, so a re-render can never cancel
  // a live stream.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleEvent = useCallback((event: ServerSentEvent) => {
    if (event.field !== "data") return;

    const parsed = LLMEventValueSchema.safeParse(event.value);
    if (!parsed.success) {
      // One malformed frame should not tear down the whole stream.
      console.warn("Unrecognised stream event:", event.value);
      return;
    }
    const value = parsed.data;

    if (value.type === "error") {
      setError(value.message);
      return;
    }

    if (value.type === "new_message") {
      if (value.message.role === "assistant") {
        activeAssistantIdRef.current = value.message.id;
      }
      setMessages((prev) => [...prev, value.message]);
      return;
    }

    if (value.type === "message_patch") {
      const { message_id, patch } = value;
      setMessages((prev) => {
        const targetIndex = prev.findIndex(({ id }) => id === message_id);
        if (targetIndex === -1) return prev;
        const targetMessage = structuredClone(prev[targetIndex]);
        const newMessage = jsonpatch.applyPatch(targetMessage, patch).newDocument;
        return [
          ...prev.slice(0, targetIndex),
          newMessage,
          ...prev.slice(targetIndex + 1),
        ];
      });
      return;
    }

    if (value.type === "llm_chunk") {
      setMessages((prev) => {
        const targetId = activeAssistantIdRef.current;
        if (!targetId) {
          const newMsg: Message = {
            id: crypto.randomUUID(),
            role: "assistant",
            content: value.content,
          };
          activeAssistantIdRef.current = newMsg.id;
          return [...prev, newMsg];
        }
        const targetIndex = prev.findIndex(({ id }) => id === targetId);
        if (targetIndex === -1) return prev;
        const target = prev[targetIndex];
        return [
          ...prev.slice(0, targetIndex),
          { ...target, content: target.content + value.content },
          ...prev.slice(targetIndex + 1),
        ];
      });
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsReading(false);
  }, []);

  const reset = useCallback(() => {
    cancel();
    setInput("");
    setError(null);
    activeAssistantIdRef.current = null;
    setMessages(initMessages);
  }, [cancel, initMessages]);

  const submit = useCallback(() => {
    if (isReading || !input.trim()) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input,
    };
    const outgoing = [...messagesRef.current, userMessage];

    setInput("");
    setError(null);
    setMessages(outgoing);
    activeAssistantIdRef.current = null;
    setIsReading(true);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    fetchChat({
      messages: outgoing,
      tools: toolsRef.current,
      modelName,
      signal: controller.signal,
    })
      .then((reader) => readTextStream({ reader, onEvent: handleEvent }))
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (abortRef.current === controller) abortRef.current = null;
        setIsReading(false);
      });
  }, [handleEvent, input, isReading, modelName]);

  return {
    messages,
    isLoading: isReading,
    isError: error !== null,
    error,
    input,
    cancel,
    reset,
    setInput,
    submit,
  };
}
