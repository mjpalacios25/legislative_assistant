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
      paths: ["/rag", ""],
    },
    {
      icon: <MessagesSquare className="size-5" />,
      label: "Policy Research",
      paths: ["/chat/research"],
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
        <Link href={"/"}>
          <Button variant="outline" size="icon" aria-label="Home">
            <Sparkles className="size-5 fill-foreground" />
          </Button>
        </Link>
      </div>
      <nav className={`grid gap-1 p-2`}>
        {buttonDetails.map(({ icon, label, paths }, index) => (
          <Tooltip.Provider key={index}>

            <Tooltip.Root key={index}>
              <Tooltip.Trigger asChild>
                <Link href={(paths ?? ["/"])[0]}>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={label}
                    className={`$rounded-lg ${paths?.includes(location) ? "bg-muted" : ""}`}
                  >
                    {icon}
                  </Button>
                </Link>
              </Tooltip.Trigger>
              <TooltipContent side="right" sideOffset={5}>
                {label}
              </TooltipContent>
            </Tooltip.Root>
          </Tooltip.Provider>
          
        ))}
      </nav>
    </aside>
  );
}