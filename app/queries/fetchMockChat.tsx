import { buildMockStream, buildSSE } from "@/app/streaming/mock";

const sampleText = `This is an extended sample of streaming text. It's designed to demonstrate how content can be gradually built up over time, character by character. This simulates the effect of a message being typed or content being loaded in real time. The purpose is to provide a visual and interactive experience for users, showcasing the dynamic nature of data processing and presentation in modern web applications.`;

export async function fetchMockChat() {
  const { reader, controller } = buildMockStream();

  function enqueueChunk(chunk: string, delay: number) {
    setTimeout(() => {
      controller.enqueue(
        buildSSE({
          field: "data",
          value: { type: "llm_chunk", content: chunk },
        }),
      );
    }, delay);
  }

  for (let i = 0; i < sampleText.length; i += 10) {
    const chunk = sampleText.substring(i, i + 10);
    const delay = 300 * (i / 10);
    enqueueChunk(chunk, delay);
  }

  return reader;
}
