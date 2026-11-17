import { UseQueryResult, useQuery } from "@tanstack/react-query";
import { fetchChat } from "./fetchChat";
import { fetchMockChat } from "./fetchMockChat";
import { Message } from "@/app/llm/types";

export function useChatQuery({
  messages,
  modelName,
  tools = [],
  endpoint = "/api/chat",
}: {
  messages: Message[];
  modelName?: string;
  tools?: string[];
  endpoint?: string;
}): UseQueryResult<ReadableStreamDefaultReader<Uint8Array>, Error> {
  const key = JSON.stringify({
    messages,
    tools,
  });
  const query = useQuery({
    queryKey: ["chat", key],
    // "in-memory" serves the local mock stream instead of the backend, which
    // loads a 9B model and connects to Neo4j at import time. See .env.example.
    queryFn: () =>
      process.env.NEXT_PUBLIC_ADAPTER_TYPE === "in-memory"
        ? fetchMockChat()
        : fetchChat({ messages, tools, endpoint, modelName }),
    // A ReadableStreamDefaultReader drains exactly once, so this result must
    // never be replayed from cache. useChat no longer uses this hook for that
    // reason; useCompletion still does. See the note in app/chat/useChat.tsx.
    staleTime: 0,
    gcTime: 0,
    retry: false,
    refetchOnMount: false,
    refetchOnWindowFocus: false,
    enabled: !!messages.filter(({ role }) => role === "user").length,
  });

  return query;
}
