import StreamedText from "@/app/llm/StreamedText";
import { Message, ToolEvent } from "@/app/llm/types";
import React, { useMemo } from "react";
import { Tool } from "./Chat";
import { Bot, User } from "lucide-react";

export function MessageGroupList({
  isLoading,
  messages,
  tools,
}: {
  isLoading: boolean;
  messages: Message[];
  tools?: Tool[];
}) {
  const messagesGroups = useMessageGroups({ messages });
  return messagesGroups.map((group, index) => {
    const role = group[0].role === "user" ? "user" : "assistant";
    const isGroupLoading =
      isLoading && index === messagesGroups.length - 1 && role !== "user";
    return (
      <MessageGroup
        key={`${group[0].id}`}
        messages={group}
        isLoading={isGroupLoading}
        role={role}
        tools={tools}
        index={index}
      />
    );
  });
}

const defaultGroupTool: Tool[] = [];

function MessageGroup({
  messages,
  index,
  role = "user",
  isLoading = false,
  tools = defaultGroupTool,
}: {
  messages: Message[];
  index: number;
  isLoading?: boolean;
  role?: "assistant" | "user";
  tools?: Tool[];
}) {
  const avatarIcon =
    role === "assistant" ? (
      <Bot className="size-5" />
    ) : (
      <User className="size-5" />
    );
  const background =
    role === "user"
      ? "bg-gray-50 "
      : "bg-gray-200 ";

  // const background =
  // role === "user"
  //   ? "bg-gray-50 dark:bg-gray-900"
  //   : "bg-gray-200 dark:bg-gray-800";
  return (
    <div
      className={`flex flex-col gap-2 px-8 py-4 ${background} ${index !== 0 ? "border-t border-gray-200" : ""}`}
    >
      <div className="flex items-center">
        {avatarIcon}
        <div className="ml-2 font-bold">
          {role === "assistant" ? "Assistant" : "User"}
        </div>
      </div>
      <div className="text-sm">
        {messages.map((message, index) => {
          if (message.role === "tool") return <></>;
          const isMessageLoading =
            isLoading &&
            index === messages.length - 1 &&
            (message.events ?? []).length === 0;
          return (
            <React.Fragment key={message.id}>
              {message.content || isMessageLoading ? (
                <StreamedText
                  text={message.content}
                  isLoading={isMessageLoading}
                />
              ) : null}
              <ToolList
                toolEvents={filterEventsToLastById(message.events ?? [])}
                tools={tools}
              />
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

function ToolList({
  toolEvents,
  tools,
}: {
  toolEvents: ToolEvent[];
  tools: Tool[];
}) {
  return toolEvents.map((event: ToolEvent) => {
    const tool = tools.find(({ name }) => name === event.name);
    if (!tool || !tool.UI) return <></>;
    return <tool.UI {...event} key={event.tool_call_id} />;
  });
}

function filterEventsToLastById(events: Record<string, unknown>[]) {
  const lastById: Record<string, any> = {};
  const order: string[] = [];

  events.forEach((event) => {
    const id = event.tool_call_id;
    if (typeof id !== "string") return;
    if (lastById[id] === undefined) {
      order.push(id);
    }
    lastById[id] = event;
  });
  return order.map((id) => lastById[id]);
}

function useMessageGroups({ messages }: { messages: Message[] }): Message[][] {
  return useMemo(() => {
    const messagesGroups = [];
    let currentGroup: Message[] = [];
    for (const message of messages) {
      if (message.role === "system") continue;
      if (message.role === "user") {
        messagesGroups.push([message]);
        currentGroup = [];
        continue;
      }
      if (currentGroup.length === 0) {
        currentGroup.push(message);
        messagesGroups.push(currentGroup);
        continue;
      }
      if (messagesGroups.at(-1)?.[0].role !== "user") {
        currentGroup.push(message);
        continue;
      }
      currentGroup = [message];
      messagesGroups.push(currentGroup);
    }
    return messagesGroups;
  }, [messages]);
}
