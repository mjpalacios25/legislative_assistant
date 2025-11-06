// import React from "react"

import Config from "./config";

export default function Header({ config = <Config /> }: { config?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-10 flex h-[57px] items-center gap-1 border-b bg-background px-4">
      <h1 className="text-xl font-semibold">AI Playground</h1>
      
    </header>
  );
}