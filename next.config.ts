import type { NextConfig } from "next";

// The backend is reached through the route handler at app/api/chat/route.ts,
// which reads BACKEND_URL itself. A rewrites() proxy was used here previously
// but buffered text/event-stream responses instead of forwarding them.
const nextConfig: NextConfig = {};

export default nextConfig;
