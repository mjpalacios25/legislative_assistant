// // polyfill used in test environment
// if (typeof TextDecoder === "undefined") {
//   // eslint-disable-next-line @typescript-eslint/no-var-requires
//   global.TextDecoder = require("text-encoding").TextDecoder;
// }

export interface ServerSentEvent {
  field: "data";
  value: Record<string, unknown> | string;
}

/** Partial implementation of https://html.spec.whatwg.org/multipage/server-sent-events.html#event-stream-interpretation */
export async function readTextStream({
  reader,
  onEvent,
}: {
  reader: ReadableStreamDefaultReader<Uint8Array>;
  onEvent: (event: ServerSentEvent) => void;
}) {
  const decoder = new TextDecoder();
  let done = false;
  let buffer = "";
  while (!done) {
    const { value, done: doneReading } = await reader.read();
    done = doneReading;
    const chunkValue = decoder.decode(value, { stream: !done });
    buffer += chunkValue;

    let pos;
    while ((pos = buffer.indexOf("\n\n")) >= 0) {
      const line = buffer.slice(0, pos);
      buffer = buffer.slice(pos + 2);

      if (line.startsWith(":")) continue;

      const index = line.indexOf(":");
      const field = line.substring(0, index);
      const raw = line.substring(index + 1); // +1 to skip the colon itself

      // Frames are assumed to carry JSON. A frame that does not parse is
      // skipped: passing the raw string on would only throw downstream in
      // schema validation and kill the whole stream over one bad frame.
      let value: Record<string, unknown> | string;
      try {
        value = JSON.parse(raw);
      } catch (e) {
        if (e instanceof SyntaxError) {
          console.warn("Skipping unparseable SSE frame:", raw);
          continue;
        }
        throw e;
      }

      switch (field) {
        case "data":
          onEvent({ field, value });
          break;
        default:
          // other fields not implemented (id, retry, ...)
          break;
      }
    }
  }
}


