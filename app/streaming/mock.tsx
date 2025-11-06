export function buildMockStream(): {
  reader: ReadableStreamDefaultReader<Uint8Array>;
  controller: ReadableStreamDefaultController<Uint8Array>;
} {
  let streamController: ReadableStreamDefaultController<Uint8Array>;
  const stream = new ReadableStream({
    start(controller) {
      streamController = controller;
    },
  });
  const reader = stream.getReader();
  return { reader, controller: streamController! };
}

export function buildSSE({ field, value }: { field: string; value: any }) {
  return new TextEncoder().encode(`${field}: ${JSON.stringify(value)}\n\n`);
}
