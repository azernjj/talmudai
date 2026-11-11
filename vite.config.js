import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    rolldownOptions: {
      input: [
        fileURLToPath(new URL('./index.html', import.meta.url)),
        fileURLToPath(new URL('./daf-hayomi.html', import.meta.url))
      ]
    }
  }
})
