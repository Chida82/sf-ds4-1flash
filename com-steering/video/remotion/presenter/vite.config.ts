import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: "presenter",
  publicDir: "../public",
  plugins: [react()],
  server: { fs: { allow: [".."] } },
});
