import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

// The UI imports the SDK straight from its source (../sdk/src). Alias it and allow
// Vite to read files outside the UI root.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@sdk": resolve(__dirname, "../sdk/src/index.ts"),
    },
  },
  server: {
    fs: { allow: [resolve(__dirname, ".."), resolve(__dirname)] },
  },
});
