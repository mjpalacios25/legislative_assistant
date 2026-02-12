export function stripThinkBlocks(text: string): string {
  let cleaned = text.replace(/<think>[\s\S]*?<\/think>\s*/g, "");
  // Strip unclosed <think> at end (still streaming)
  const lastOpen = cleaned.lastIndexOf("<think>");
  if (lastOpen !== -1 && cleaned.indexOf("</think>", lastOpen) === -1) {
    cleaned = cleaned.substring(0, lastOpen);
  }
  return cleaned;
}
