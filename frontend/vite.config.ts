import path from "path"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
      host: '0.0.0.0',
      port: 5173,
      watch: {
        usePolling: true
      },
      proxy: {
        '/api': {
          target: 'http://backend:8000',
          changeOrigin: true,
          secure: false
        }
      }
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
})
