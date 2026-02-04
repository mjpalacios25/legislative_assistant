import { Sparkles } from "lucide-react";

export default function Header() {
  return (
    <header className="sticky top-0 z-10 flex h-[57px] items-center gap-2 border-b bg-background px-4">
      <Sparkles className="size-5" />
      <h1 className="text-xl font-semibold">AI Legislative Assistant</h1>
    </header>
  );
}
