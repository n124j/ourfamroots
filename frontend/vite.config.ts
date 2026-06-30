import {resolve} from 'path';
import {defineConfig, loadEnv} from 'vite';

import react from '@vitejs/plugin-react';

// Minimal Node.js process typing — avoids requiring @types/node.
declare const process: {env: Record<string, string | undefined>};

export default defineConfig(({mode}) => {
    const envDir = resolve(__dirname, '..');
    // Load ALL vars from .env (empty prefix = no VITE_ filtering)
    const fileEnv = loadEnv(mode, envDir, '');

    // Which hostnames the Vite dev server accepts.
    const _hosts = (
        process.env.VITE_ALLOWED_HOSTS ??
        fileEnv.VITE_ALLOWED_HOSTS ??
        ''
    ).trim();
    const allowedHosts: true | string[] | undefined =
        _hosts === 'all'
            ? true
            : _hosts
              ? _hosts
                    .split(',')
                    .map((h: string) => h.trim())
                    .filter(Boolean)
              : undefined;

    return {
        plugins: [react()],
        envDir,
        define: {
            'import.meta.env.VITE_GOOGLE_CLIENT_ID': JSON.stringify(
                process.env.VITE_GOOGLE_CLIENT_ID ||
                    process.env.GOOGLE_CLIENT_ID ||
                    fileEnv.VITE_GOOGLE_CLIENT_ID ||
                    fileEnv.GOOGLE_CLIENT_ID ||
                    '',
            ),
            'import.meta.env.VITE_GITHUB_CLIENT_ID': JSON.stringify(
                process.env.VITE_GITHUB_CLIENT_ID ||
                    process.env.GITHUB_CLIENT_ID ||
                    fileEnv.VITE_GITHUB_CLIENT_ID ||
                    fileEnv.GITHUB_CLIENT_ID ||
                    '',
            ),
        },
        resolve: {
            alias: {
                '@pages': resolve(__dirname, 'src/pages'),
                '@shared': resolve(__dirname, 'src/shared'),
                '@store': resolve(__dirname, 'src/store'),
                '@api': resolve(__dirname, 'src/api'),
                '@features': resolve(__dirname, 'src/features'),
                '@queries': resolve(__dirname, 'src/queries'),
                '@extensions': resolve(__dirname, 'src/extensions'),
            },
        },
        server: {
            host: '0.0.0.0',
            port: 5173,
            watch: { usePolling: true, interval: 300 },
            ...(allowedHosts && {allowedHosts}),
            proxy: {
                '/api/v1': {
                    target:
                        process.env.VITE_API_PROXY_TARGET ??
                        fileEnv.VITE_API_PROXY_TARGET ??
                        'http://localhost:7004',
                    changeOrigin: true,
                },
            },
        },
    };
});
