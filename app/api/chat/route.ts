// Next's `rewrites()` proxy buffers `text/event-stream` responses instead of
// forwarding them, so the browser received nothing until the whole generation
// finished (and in practice, not even then). This route handler pipes the
// upstream body straight through, which keeps the stream intact.

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: Request) {
  const upstream = await fetch(`${BACKEND_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: await req.text(),
    signal: req.signal,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(
      JSON.stringify({ error: `Backend returned ${upstream.status}` }),
      { status: upstream.status, headers: { "Content-Type": "application/json" } },
    );
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      // Tells nginx and friends not to buffer the stream.
      "X-Accel-Buffering": "no",
    },
  });
}
