import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Всё слушаем только на 127.0.0.1. Запросы /api браузер шлёт на тот же адрес,
// а Vite пересылает их на бэкенд, поэтому CORS в dev-режиме даже не нужен.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
