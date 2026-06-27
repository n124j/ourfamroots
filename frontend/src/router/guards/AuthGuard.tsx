/**
 * AuthGuard — redirects unauthenticated users to /login.
 *
 * Waits for the silent-refresh attempt to complete (isInitialised)
 * before deciding whether to render children or redirect.
 * This prevents a flash-of-login-page on hard refresh.
 */

import React, { lazy, Suspense } from 'react';
import { Navigate, Outlet, useLocation, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '@store/auth.store';
import { useMaintenanceStore } from '@store/maintenance.store';

const MaintenancePage = lazy(() => import('@pages/MaintenancePage'));

export function AuthGuard() {
  const isAuthenticated   = useAuthStore((s) => s.isAuthenticated);
  const isInitialised     = useAuthStore((s) => s.isInitialised);
  const user              = useAuthStore((s) => s.user);
  const isMaintenanceMode = useMaintenanceStore((s) => s.isMaintenanceMode);
  const location          = useLocation();

  // Still attempting silent token refresh — show nothing (or a spinner)
  if (!isInitialised) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-white">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  }

  if (isMaintenanceMode && user?.appRole !== 'SUPER_ADMIN') {
    return (
      <Suspense fallback={null}>
        <MaintenancePage />
      </Suspense>
    );
  }

  return <Outlet />;
}

/**
 * GuestGuard — redirects already-authenticated users away from /login.
 * During maintenance, non-super-admin users see the maintenance page
 * instead of being redirected to login.
 */
export function GuestGuard() {
  const isAuthenticated   = useAuthStore((s) => s.isAuthenticated);
  const isInitialised     = useAuthStore((s) => s.isInitialised);
  const user              = useAuthStore((s) => s.user);
  const isMaintenanceMode = useMaintenanceStore((s) => s.isMaintenanceMode);
  const [searchParams]    = useSearchParams();

  if (!isInitialised) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-white">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isAuthenticated) {
    if (isMaintenanceMode && user?.appRole !== 'SUPER_ADMIN') {
      return (
        <Suspense fallback={null}>
          <MaintenancePage />
        </Suspense>
      );
    }
    const next = searchParams.get('next') || '/dashboard';
    return <Navigate to={next} replace />;
  }

  // Show maintenance page to unauthenticated visitors during maintenance
  if (isMaintenanceMode) {
    return (
      <Suspense fallback={null}>
        <MaintenancePage />
      </Suspense>
    );
  }

  return <Outlet />;
}
