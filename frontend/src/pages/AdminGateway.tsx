/**
 * AdminLoginPage — standalone login form at /admin/login.
 *
 * Only functional when the site is in maintenance mode.
 * After successful Super Admin login, redirects to /admin (AuthGuard + AppShell).
 * When the site is live, redirects away.
 */
import React, { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@store/auth.store';
import { useMaintenanceStore } from '@store/maintenance.store';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export default function AdminLoginPage() {
  const navigate       = useNavigate();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isInitialised   = useAuthStore((s) => s.isInitialised);
  const user            = useAuthStore((s) => s.user);
  const storeLogin      = useAuthStore((s) => s.login);
  const isMaintenanceMode = useMaintenanceStore((s) => s.isMaintenanceMode);
  const setMaintenance    = useMaintenanceStore((s) => s.setMaintenance);

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [error,    setError]    = useState('');
  const [loading,  setLoading]  = useState(false);

  // Still loading auth state
  if (!isInitialised) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-white">
        <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Already logged in → go to admin dashboard
  if (isAuthenticated && (user?.appRole === 'SUPER_ADMIN' || user?.appRole === 'ADMIN')) {
    return <Navigate to="/admin" replace />;
  }

  // Site is live → this page is not needed
  if (!isMaintenanceMode) {
    return <Navigate to="/login?next=/admin" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail ?? 'Invalid email or password');
      }
      const data = await res.json();

      const meRes = await fetch(`${API_BASE}/users/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
        credentials: 'include',
      });
      const me = meRes.ok ? await meRes.json() : null;
      const role = me?.app_role ?? 'STANDARD';

      if (role !== 'SUPER_ADMIN') {
        setError('Only the Super Administrator can sign in during maintenance mode.');
        return;
      }

      storeLogin(data.access_token, {
        id: data.user_id,
        tenantId: data.tenant_id,
        email,
        displayName: me ? `${me.given_name ?? ''} ${me.family_name ?? ''}`.trim() || email : email,
        avatarUrl: me?.avatar_url ?? undefined,
        isEmailVerified: true,
        appRole: role,
        language: me?.locale,
        theme: me?.theme,
      });

      // Refresh maintenance status
      try {
        const maintRes = await fetch(`${API_BASE}/site-settings/maintenance`, {
          headers: { Authorization: `Bearer ${data.access_token}` },
          credentials: 'include',
        });
        if (maintRes.ok) {
          const maintData = await maintRes.json();
          setMaintenance(maintData.maintenance_mode, maintData.maintenance_message);
        }
      } catch { /* ignore */ }

      navigate('/admin', { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="w-full max-w-sm mx-4">
        <div className="bg-white rounded-2xl shadow-xl border border-slate-200 p-8">
          {/* Header */}
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-amber-100 mb-3">
              <svg className="w-7 h-7 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-slate-900">Admin Access</h1>
            <p className="text-sm text-slate-500 mt-1">
              Site is under maintenance. Sign in as Super Administrator.
            </p>
          </div>

          {error && (
            <div className="mb-4 px-3 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                placeholder="admin@example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full h-10 px-3 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500"
                placeholder="Enter your password"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full h-10 bg-amber-500 text-white text-sm font-semibold rounded-lg hover:bg-amber-600 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-400 mt-4">
          OurFamRoots — Super Administrator Access
        </p>
      </div>
    </div>
  );
}
