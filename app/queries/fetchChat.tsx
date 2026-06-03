import { Message } from "@/app/llm/types";

const BASE_API_URL = process.env.NEXT_PUBLIC_API_URL;
if (!BASE_API_URL) throw new Error("NEXT_PUBLIC_API_URL is not set");

export async function fetchChat({
  messages,
  modelName = "Qwen/Qwen3-4B-MLX-4bit",
  tools = [],
  endpoint = "/api/chat",
}: {
  messages: Message[];
  modelName?: string;
  tools?: string[];
  endpoint?: string;
}): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  const fetchOptions = {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ messages, tools, model_name: modelName }),
  };

  const response = await fetch(`${BASE_API_URL}${endpoint}`, fetchOptions);
  if (!response.ok || !response.body) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.body.getReader();
}
