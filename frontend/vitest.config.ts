import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@pages':    resolve(__dirname, 'src/pages'),
      '@shared':   resolve(__dirname, 'src/shared'),
      '@store':    resolve(__dirname, 'src/store'),
      '@api':      resolve(__dirname, 'src/api'),
      '@features': resolve(__dirname, 'src/features'),
      '@queries':  resolve(__dirname, 'src/queries'),
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
