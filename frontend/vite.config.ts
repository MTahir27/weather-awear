/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // In development the Django API runs separately; in production both are
    // served from the same Vercel origin, so the client always calls `/api`.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  build: {
    // MapLibre alone is ~1 MB minified and cannot be split further; it is
    // lazy-loaded with the map, so it does not delay the first render.
    chunkSizeWarningLimit: 1200,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
