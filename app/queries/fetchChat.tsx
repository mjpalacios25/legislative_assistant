import { Message } from "@/app/llm/types";

// Empty means "same origin": requests go to /api/* on the Next.js server, which
// rewrites them through to FastAPI (see next.config.ts). Set NEXT_PUBLIC_API_URL
// only when the backend must be reached directly at an absolute URL.
const BASE_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export async function fetchChat({
  messages,
  modelName = "Qwen/Qwen3-4B-MLX-4bit",
  tools = [],
  endpoint = "/api/chat",
  signal,
}: {
  messages: Message[];
  modelName?: string;
  tools?: string[];
  endpoint?: string;
  signal?: AbortSignal;
}): Promise<ReadableStreamDefaultReader<Uint8Array>> {
  const fetchOptions = {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ messages, tools, model_name: modelName }),
    signal,
  };

  const response = await fetch(`${BASE_API_URL}${endpoint}`, fetchOptions);
  if (!response.ok || !response.body) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return response.body.getReader();
}
