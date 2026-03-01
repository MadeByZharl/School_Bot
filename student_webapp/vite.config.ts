import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/student/',
  plugins: [react()],
  build: {
    outDir: '../static_student',
    emptyOutDir: true
  }
})
