import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El front consume la API del pipeline (pipeline.server). Configurable por VITE_API_BASE.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, host: true },
})
