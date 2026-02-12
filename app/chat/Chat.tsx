"use client";

import { Textarea } from "@/app/components/textarea";
import { Button } from "@/app/components/button";
import { useChat } from "./useChat";
import { Label } from "@/app/components/label";
import { Message } from "@/app/llm/types";
import { MessageGroupList } from "./MessageGroupList";
import { CornerDownLeft } from "lucide-react";
import { useEffect, useRef, KeyboardEvent } from "react";

export interface Tool {
  name: string;
  UI?: (props: any) => JSX.Element;

}const defaultInitMessages: Message[] = [];
const defaultTools: Tool[] = [];

export function Chat({
  tools = defaultTools,
  initMessages = defaultInitMessages,
  modelName,
}: {
  tools?: Tool[];
  initMessages?: Message[];
  modelName?: string;
}) {
  const { messages, submit, input, setInput, isLoading } = useChat({
    initMessages,
    tools: tools.map(({name}) => name),
    modelName
  });

  const { messagesEndRef } = useScrollToMessage({ messages });

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && input.trim()) {
        submit();
      }
    }
  };

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl bg-white shadow-sm mb-4">
      <div className="flex flex-1 flex-col overflow-y-auto">
        <MessageGroupList 
          messages={messages} 
          isLoading={isLoading} 
          tools={tools}
        />
        <div ref={messagesEndRef} className="h-2" />
      </div>
      <form 
        className="relative mx-4 overflow-hidden rounded-lg border bg-background focus-within:ring-1 focus-within:ring-ring"
        x-chunk="dashboard-03-chunk-1"
      >
        <Label htmlFor="message" className="sr-only">
          Message
        </Label>
        <Textarea
          id="message"
          placeholder="Type your message here..."
          className="min-h-12 resize-none border-0 p-3 shadow-none focus-visible:ring-0"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="flex items-center p-3 pt-0">
          <Button
            type="submit"
            size="sm"
            className="ml-auto gap-1.5"
            onClick={() => submit()}
            disabled={isLoading || !input}
          >
            Send Message
            <CornerDownLeft className="size-3.5" />
          </Button>
        </div>
      </form>
    </div>
  );
}

function useScrollToMessage({ messages }: { messages: Message[] }) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView();
  }, [messages]);

  return { messagesEndRef };
}

// function MessageList({
//   isLoading,
//   messages,
// }: {
//   isLoading: boolean;
//   messages: Message[];
// }) {
//   return messages.map((message, index) => {
//     const role = message.role === "user" ? "user" : "assistant";
//     return (
//       <MessageBlock
//         key={message.id}
//         message={message}
//         isLoading={
//           isLoading && index === messages.length - 1 && role !== "user"
//         }
//         role={role}
//         index={index}
//       />
//     );
//   });
// }

// function MessageBlock({
//   message,
//   index,
//   role = "user",
//   isLoading = false,
// }: {
//   message: Message;
//   index: number;
//   isLoading?: boolean;
//   role?: "assistant" | "user";
// }) {
//   const avatarIcon =
//     role === "assistant" ? (
//       <Bot className="size-5" />
//     ) : (
//       <User className="size-5" />
//     );
//   const background =
//     index % 2 === 0
//       ? "bg-gray-100 dark:bg-gray-800"
//       : "bg-gray-50 dark:bg-gray-900";
//   return (
//     <div
//       className={`flex flex-col gap-2 px-8 py-4 ${background} ${index !== 0 ? "border-t border-gray-200" : ""}`}
//     >
//       <div className="flex items-center">
//         {avatarIcon}
//         <div className="ml-2 font-bold">
//           {role === "assistant" ? "Assistant" : "User"}
//         </div>
//       </div>
//       <div className="text-sm">
//         {message.content || isLoading ? (
//           <StreamedText text={message.content} isLoading={isLoading} />
//         ) : null}
//       </div>
//     </div>
//   );
// }
