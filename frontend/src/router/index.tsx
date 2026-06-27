/**
 * Application router — React Router v6 with lazy-loaded pages.
 *
 * Route tree:
 *   /login, /register, /reset-password, /auth/callback  → GuestGuard (or public)
 *   /*                                                   → AuthGuard
 *     /dashboard
 *     /trees/:treeId                                     → full-screen canvas
 *     /trees/:treeId/persons/:personId
 *     /search
 *     /reports
 *     /settings/*
 */

import React, { lazy, Suspense } from 'react';
import { createBrowserRouter, RouterProvider, Outlet } from 'react-router-dom';
import { AuthGuard, GuestGuard } from './guards/AuthGuard';
import { useMaintenanceStore } from '@store/maintenance.store';
import { useAuthStore } from '@store/auth.store';

// ── Lazy pages ─────────────────────────────────────────────────────────────

const LoginPage           = lazy(() => import('@pages/auth/LoginPage'));
const RegisterPage        = lazy(() => import('@pages/auth/RegisterPage'));
const OAuthCallbackPage   = lazy(() => import('@pages/auth/OAuthCallbackPage'));
const ForgotPasswordPage  = lazy(() => import('@pages/auth/ForgotPasswordPage'));
const ResetPasswordPage   = lazy(() => import('@pages/auth/ResetPasswordPage'));
const VerifyEmailPage     = lazy(() => import('@pages/auth/VerifyEmailPage'));
const VerifyNewLoginPage  = lazy(() => import('@pages/auth/VerifyNewLoginPage'));

const DashboardPage           = lazy(() => import('@pages/DashboardPage'));
const InvitationAcceptPage    = lazy(() => import('@pages/InvitationAcceptPage'));
const FamilyTreePage     = lazy(() => import('@pages/FamilyTreePage'));
const ProfilePage        = lazy(() => import('@pages/ProfilePage'));
const SearchPage         = lazy(() => import('@pages/SearchPage'));
const ReportsPage        = lazy(() => import('@pages/ReportsPage'));
const SettingsPage       = lazy(() => import('@pages/SettingsPage'));
const ActivityPage       = lazy(() => import('@pages/ActivityPage'));
const AdminPage          = lazy(() => import('@pages/AdminPage'));
const AdminLoginPage     = lazy(() => import('@pages/AdminGateway'));
const MaintenancePage    = lazy(() => import('@pages/MaintenancePage'));
const NotFoundPage       = lazy(() => import('@pages/NotFoundPage'));
const ContactPage        = lazy(() => import('@pages/ContactPage'));
const TermsPage          = lazy(() => import('@pages/TermsPage'));
const PrivacyPage        = lazy(() => import('@pages/PrivacyPage'));
const HelpPage           = lazy(() => import('@pages/HelpPage'));
const LandingPage           = lazy(() => import('@pages/LandingPage'));
const ConfirmDeletionPage   = lazy(() => import('@pages/ConfirmDeletionPage'));
const SharedTreePage        = lazy(() => import('@pages/SharedTreePage'));
const DiscoverPage          = lazy(() => import('@pages/DiscoverPage'));
const DiscoverTreePage      = lazy(() => import('@pages/DiscoverTreePage'));

// AppShell wraps all authenticated routes (sidebar + topbar)
const AppShell           = lazy(() => import('@shared/components/layout/AppShell'));

// ── Suspense wrapper ───────────────────────────────────────────────────────

function PageLoader() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-surface-muted">
      <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function Lazy({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>;
}

/**
 * PublicMaintenanceGuard — shows maintenance page on public routes
 * when the site is under construction (unless the user is Super Admin).
 */
function PublicMaintenanceGuard() {
  const isMaintenanceMode = useMaintenanceStore((s) => s.isMaintenanceMode);
  const user              = useAuthStore((s) => s.user);

  if (isMaintenanceMode && user?.appRole !== 'SUPER_ADMIN') {
    return <Lazy><MaintenancePage /></Lazy>;
  }
  return <Outlet />;
}

// ── Router definition ──────────────────────────────────────────────────────

const router = createBrowserRouter([
  // ── Public / guest routes ──────────────────────────────────────────────
  {
    element: <GuestGuard />,
    children: [
      { path: '/login',            element: <Lazy><LoginPage /></Lazy> },
      { path: '/register',         element: <Lazy><RegisterPage /></Lazy> },
      { path: '/forgot-password',  element: <Lazy><ForgotPasswordPage /></Lazy> },
      { path: '/reset-password',   element: <Lazy><ResetPasswordPage /></Lazy> },
      { path: '/verify-email',     element: <Lazy><VerifyEmailPage /></Lazy> },
    ],
  },

  // ── Landing page (public — redirects to /dashboard if already authed) ──
  {
    element: <PublicMaintenanceGuard />,
    children: [
      { path: '/', element: <Lazy><LandingPage /></Lazy> },
    ],
  },

  // ── Public informational pages (no auth required) ────────────────────
  {
    path: '/help',
    element: <Lazy><HelpPage /></Lazy>,
  },
  {
    path: '/contact',
    element: <Lazy><ContactPage /></Lazy>,
  },
  {
    path: '/terms',
    element: <Lazy><TermsPage /></Lazy>,
  },
  {
    path: '/privacy',
    element: <Lazy><PrivacyPage /></Lazy>,
  },

  // ── Login verification (public — token arrives here from email) ─────────
  {
    path: '/verify-new-login',
    element: <Lazy><VerifyNewLoginPage /></Lazy>,
  },

  // ── Account deletion confirmation (public — token arrives here) ─────────
  {
    path: '/confirm-deletion',
    element: <Lazy><ConfirmDeletionPage /></Lazy>,
  },

  // ── Public shared tree viewer (no auth required) ──────────────────────
  {
    path: '/shared/:shareToken',
    element: <Lazy><SharedTreePage /></Lazy>,
  },

  // ── OAuth callback (public — token arrives here) ───────────────────────
  {
    path: '/auth/callback',
    element: <Lazy><OAuthCallbackPage /></Lazy>,
  },

  // ── Invitation accept (public — handles its own auth check) ──────────
  {
    path: '/invitations/accept',
    element: <Lazy><InvitationAcceptPage /></Lazy>,
  },

  // ── Admin login (public — only works during maintenance mode) ─────────
  {
    path: '/admin/login',
    element: <Lazy><AdminLoginPage /></Lazy>,
  },

  // ── Full-screen tree canvas (authenticated, no AppShell) ──────────────
  {
    element: <AuthGuard />,
    children: [
      {
        path: '/trees/:treeId',
        element: <Lazy><FamilyTreePage /></Lazy>,
      },
      {
        path: '/discover/trees/:treeId',
        element: <Lazy><DiscoverTreePage /></Lazy>,
      },
    ],
  },

  // ── Standard authenticated routes (AuthGuard + AppShell) ──────────────
  {
    element: <AuthGuard />,
    children: [
      {
        element: <Lazy><AppShell /></Lazy>,
        children: [
          { path: '/dashboard',                              element: <Lazy><DashboardPage /></Lazy> },
          { path: '/trees/:treeId/persons/:personId',        element: <Lazy><ProfilePage /></Lazy> },
          { path: '/search',                                 element: <Lazy><SearchPage /></Lazy> },
          { path: '/discover',                                element: <Lazy><DiscoverPage /></Lazy> },
          { path: '/reports',                                element: <Lazy><ReportsPage /></Lazy> },
          { path: '/settings',                               element: <Lazy><SettingsPage /></Lazy> },
          { path: '/settings/:tab',                          element: <Lazy><SettingsPage /></Lazy> },
          { path: '/activity',                               element: <Lazy><ActivityPage /></Lazy> },
          { path: '/admin',                                  element: <Lazy><AdminPage /></Lazy> },
        ],
      },
    ],
  },

  // ── 404 ───────────────────────────────────────────────────────────────
  { path: '*', element: <Lazy><NotFoundPage /></Lazy> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
