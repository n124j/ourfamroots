import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  // Vite's default env loading pulls process.env.VITE_* into import.meta.env,
  // which picks up VITE_API_BASE_URL from the docker-compose dev-server
  // environment (an absolute http://localhost:PORT URL) when tests run
  // inside that container. Pin it to the relative default here so tests are
  // hermetic and match what MSW's path-only request handlers expect,
  // regardless of the host shell's environment.
  define: {
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/api/v1'),
  },
  resolve: {
    alias: {
      '@pages':    resolve(__dirname, 'src/pages'),
      '@shared':   resolve(__dirname, 'src/shared'),
      '@store':    resolve(__dirname, 'src/store'),
      '@api':      resolve(__dirname, 'src/api'),
      '@features': resolve(__dirname, 'src/features'),
      '@queries':  resolve(__dirname, 'src/queries'),
      '@extensions': resolve(__dirname, 'src/extensions'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    exclude: ['e2e/**', 'node_modules/**'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**'],
      exclude: ['src/**/*.{test,spec}.{ts,tsx}', 'src/types/**'],
    },
  },
});
