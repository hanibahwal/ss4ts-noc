import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'vendor-react',
              test:
                /node_modules[\\/](?:react|react-dom|react-router|react-router-dom|scheduler)[\\/]/,
              priority: 30,
            },
            {
              name: 'vendor-charts',
              test:
                /node_modules[\\/](?:recharts|d3-[^\\/]+|victory-vendor|decimal\.js-light|react-is)[\\/]/,
              priority: 20,
              minSize: 20 * 1024,
              maxSize: 240 * 1024,
            },
            {
              name: 'vendor-icons',
              test:
                /node_modules[\\/]lucide-react[\\/]/,
              priority: 15,
            },
          ],
        },
      },
    },
  },
})
