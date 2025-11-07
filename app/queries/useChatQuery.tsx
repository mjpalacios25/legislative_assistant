import { UseQueryResult, 
  useQuery,
  QueryClientProvider } from "@tanstack/react-query";
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
    queryFn: () =>
      process.env.NEXT_PUBLIC_ADAPTER_TYPE === "in-memory"
        ? fetchMockChat()
        : fetchChat({ messages, tools, endpoint, modelName }),
    staleTime: Infinity,
    enabled: !!messages.filter(({ role }) => role === "user").length,
  });

  return query;
}
