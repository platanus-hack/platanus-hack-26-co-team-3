import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dashboard reads demo-api's consistency verdict straight from the browser
// (the Live screen shows it beside the agent tree). The deployed demo-api
// doesn't send CORS headers yet, so in dev we proxy those calls through Vite
// instead: same-origin for the browser, no preflight, and it keeps working
// whether or not the deployment has been refreshed.
//
// Set VITE_DEMO_API_URL to bypass this and call an origin directly.
const DEMO_API_TARGET = process.env.DEMO_API_TARGET ?? 'https://roxygt.lat'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/demo-api': {
        target: DEMO_API_TARGET,
        changeOrigin: true,
        secure: true,
      },
    },
  },
})
