'use client'

import { Input } from "../components/input";
import { Button } from "../components/button";
import { useState } from "react";
import Query from "./query";

export default function Completion() {
  const [value, setValue] = useState<string>("To be or not to be.");
  const [text, setText] = useState<string>("");
  return (
    <div
      className="flex h-full w-full items-center justify-center"
      style={{ height: "calc(100% - 57px)" }}
    >
      <div className="w-72">
        <div className="flex items-center space-x-2">
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Enter your text."
            type="text"
          />
          <Button onClick={() => setText(value)}>Emojify 🪄</Button>
        </div>
        <div className="m-2 h-8">{text ? <Query text={text} /> : null}</div>
      </div>
    </div>
  );
}