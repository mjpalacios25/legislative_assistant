import { Message } from "@/app/llm/types";

const BASE_API_URL =
  // import.meta.env.VITE_BASE_API_URL || 
  // import.meta.env.VITE_NEWLINE_APP_BACKEND_URL || 
  "http://localhost:8000";

export async function fetchChat({
  messages,
  modelName = "Qwen/Qwen3-4B-MLX-4bit", //if using Claude, insert model name here
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
  console.log("response from fetch chat", response)
  if (!response || !response.ok || !response.body) {
    throw new Error(`Invalid response: ${response}`);
  }

  // This data is a ReadableStream
  // https://developer.mozilla.org/en-US/docs/Web/API/ReadableStream
  const readableStream = response.body;
  return readableStream.getReader();
}
