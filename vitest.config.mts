import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

// Lives at the repo root so `pnpm test` (which runs `vitest` from the root)
// actually discovers it. Previously it sat in app/ and was never loaded, so
// tests ran without jsdom or the @/* path aliases.
export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["app/**/*.{test,spec}.{ts,tsx}"],
  },
});
