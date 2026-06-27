/**
 * Application bootstrap.
 *
 * Order of operations:
 *  1. Create React Query client
 *  2. Attempt silent token refresh (initAuth) — recovers session on hard reload
 *  3. Mark auth store as initialised → AuthGuard stops showing spinner
 *  4. Render the router
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { HelmetProvider } from 'react-helmet-async';

import { AppRouter } from './router';
import { initAuth } from './store/auth.store';
import { checkMaintenanceStatus } from './store/maintenance.store';
import './i18n';
import './index.css';

// ── React Query client ─────────────────────────────────────────────────────

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,            // 1 min default
      retry: (count, error: any) =>
        count < 2 && error?.status !== 401 && error?.status !== 404,
      refetchOnWindowFocus: false,  // avoids canvas re-renders
    },
    mutations: {
      onError: (error: any) => {
        // Global mutation error → push toast (wired in later)
        console.error('[mutation]', error?.message ?? error);
      },
    },
  },
});

// ── Boot sequence ──────────────────────────────────────────────────────────

async function boot() {
  // Recover session + check maintenance status before first render
  await Promise.all([initAuth(), checkMaintenanceStatus()]);

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <HelmetProvider>
        <QueryClientProvider client={queryClient}>
          <AppRouter />
          {import.meta.env.VITE_ENABLE_DEVTOOLS === 'true' && (
            <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-left" />
          )}
        </QueryClientProvider>
      </HelmetProvider>
    </React.StrictMode>
  );
}

boot();
