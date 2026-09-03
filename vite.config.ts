// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - TanStack devtools (dev-only, first), tanstackStart, viteReact, tailwindcss, tsConfigPaths,
//     nitro (build-only using cloudflare as a default target), VITE_* env injection, @ path alias,
//     React/TanStack dedupe, error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  vite: {
    define: {
      "process.env.SUPABASE_URL": JSON.stringify("https://mxldzvzsdexwtzfnfqzo.supabase.co"),
      "process.env.SUPABASE_PUBLISHABLE_KEY": JSON.stringify(
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im14bGR6dnpzZGV4d3R6Zm5mcXpvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg0NjM0MjIsImV4cCI6MjEwNDAzOTQyMn0.bohWC7ASGdWieHtBsNgocFdY1t9IOvA5qD0rWCBnhCo",
      ),
    },
  },
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
