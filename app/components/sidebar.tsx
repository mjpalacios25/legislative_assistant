'use client'

import {Button} from './button';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Code,
  Database,
  MessageCircleQuestion,
  MessagesSquare,
  Smile,
  Sparkles,
  Wrench,
} from "lucide-react";
import {  TooltipContent } from "./tooltip";
import {Tooltip} from "radix-ui";



export default function Sidebar() {
  const buttonDetails = [
    // {
    //   icon: <Smile className="size-5" />,
    //   label: "Search",
    //   paths: ["/completion", "/", ""],
    // },
     {
      icon: <MessageCircleQuestion className="size-5" />,
      label: "Legislative Q&A",
      paths: ["/", ""],
    },
    {
      icon: <MessagesSquare className="size-5" />,
      label: "Policy Research",
      paths: ["/rag/research"],
    },
    // {
    //   icon: <Wrench className="size-5" />,
    //   label: "Tools",
    //   paths: ["/llm-with-tools"],
    // },
    // {
    //   icon: <Code className="size-5" />,
    //   label: "Code",
    //   paths: ["/code"],
    // },
    // {
    //   icon: <Database className="size-5" />,
    //   label: "Talk to data",
    //   paths: ["/talk-to-data"],
    // },
  ];

  const location = usePathname();

  return (
    <aside className="inset-y fixed left-0 z-20 flex h-full flex-col border-r">
      <div className="border-b p-2">
        <Button asChild variant="outline" size="icon" aria-label="Home">
          <Link href="/">
            <Sparkles className="size-5 fill-foreground" />
          </Link>
        </Button>
      </div>
      <Tooltip.Provider>
        <nav className="grid gap-1 p-2">
          {buttonDetails.map(({ icon, label, paths }, index) => (
            <Tooltip.Root key={index}>
              <Tooltip.Trigger asChild>
                {/* Button renders the Link via Slot, so this is a single <a>.
                    Nesting <button> inside <a> is invalid content nesting. */}
                <Button
                  asChild
                  variant="ghost"
                  size="icon"
                  aria-label={label}
                  className={`rounded-lg ${paths?.includes(location) ? "bg-muted" : ""}`}
                >
                  <Link href={(paths ?? ["/"])[0]}>{icon}</Link>
                </Button>
              </Tooltip.Trigger>
              <TooltipContent side="right" sideOffset={5}>
                {label}
              </TooltipContent>
            </Tooltip.Root>
          ))}
        </nav>
      </Tooltip.Provider>
    </aside>
  );
}