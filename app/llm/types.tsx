import { z } from "zod";

export interface QueryResult<T> {
  data: T | undefined;
  isLoading: boolean;
  isError: boolean;
}

const toolEventSchema = z.object({
  tool_call_id: z.string(),
  status: z.union([
    z.literal("success"),
    z.literal("error"),
    z.literal("loading"),
  ]),
  name: z.string(),
  args: z.any(),
  data: z.any().optional(),
});

const functionSchema = z.object({
  name: z.string(),
  // Arguments are expected to be a string in JSON format.
  arguments: z.string(),
});

const toolCallSchema = z.object({
  index: z.number(),
  id: z.string(),
  type: z.literal("function"),
  function: functionSchema,
});

const messageSchema = z.object({
  id: z.string(),
  role: z.union([
    z.literal("assistant"),
    z.literal("function"),
    z.literal("tool"),
    z.literal("system"),
    z.literal("user"),
  ]),
  content: z.string(),
  events: z.array(toolEventSchema).optional(),
  tool_calls: z.array(toolCallSchema).optional(),
  tool_call_id: z.string().optional(),
});

export type ToolEvent = z.infer<typeof toolEventSchema>;
export type Message = z.infer<typeof messageSchema>;

export type UseChatQuery = ({
  messages,
  modelName,
  tools,
  endpoint,
}: {
  messages: Message[];
  modelName?: string;
  tools?: string[];
  endpoint?: string;
}) => QueryResult<ReadableStreamDefaultReader<Uint8Array>>;

export const LLMChunkSchema = z.object({
  type: z.literal("llm_chunk"),
  content: z.string(),
});

const messagePatchSchema = z.object({
  message_id: z.string(),
  patch: z.any(),
  type: z.literal("message_patch"),
});

const newMessageSchema = z.object({
  message: messageSchema,
  type: z.literal("new_message"),
});

export const LLMEventValueSchema = z.discriminatedUnion("type", [
  LLMChunkSchema,
  messagePatchSchema,
  newMessageSchema,
]);

const ChatCompletionChunkChoiceDeltaSchema = z.object({
  content: z.string(),
});

const ChatCompletionChunkChoiceSchema = z.object({
  index: z.number(),
  delta: ChatCompletionChunkChoiceDeltaSchema,
});

export const OpenAIChatCompletionChunkSchema = z.object({
  object: z.literal("chat.completion.chunk"), // Ensures the value is exactly "chat.completion.chunk"
  choices: z.array(ChatCompletionChunkChoiceSchema).nonempty(), // Ensures there's at least one choice
});

export type OpenAIChatCompletionChunk = z.infer<
  typeof OpenAIChatCompletionChunkSchema
>;
