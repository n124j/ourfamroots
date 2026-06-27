/**
 * Unit tests for OAuthCallbackPage.
 * Verifies token extraction, user fetch, store login, and error redirects.
 */
import React from 'react';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { useAuthStore } from '@store/auth.store';
import OAuthCallbackPage from '@pages/auth/OAuthCallbackPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

function renderCallback(search: string) {
  return render(
    <MemoryRouter initialEntries={[`/auth/callback${search}`]}>
      <Routes>
        <Route path="/auth/callback" element={<OAuthCallbackPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('OAuthCallbackPage', () => {
  beforeEach(() => {
    useAuthStore.setState({
      accessToken: null,
      user: null,
      isInitialised: false,
      isAuthenticated: false,
    });
    mockNavigate.mockReset();
    mockFetch.mockReset();
  });

  it('redirects to /login with error when no access_token', async () => {
    renderCallback('');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        '/login?error=oauth_failed',
        { replace: true }
      );
    });
  });

  it('redirects to /login when error param is present', async () => {
    renderCallback('?error=oauth_cancelled');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        '/login?error=oauth_cancelled',
        { replace: true }
      );
    });
  });

  it('fetches /users/me and stores user on success', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 'user-1',
        tenant_id: 'tenant-1',
        email: 'alice@example.com',
        given_name: 'Alice',
        family_name: 'Smith',
        avatar_url: 'https://example.com/avatar.png',
        email_verified: true,
        app_role: 'STANDARD',
      }),
    });

    renderCallback('?access_token=test-jwt-token&provider=google');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true });
    });

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe('test-jwt-token');
    expect(state.user?.email).toBe('alice@example.com');
    expect(state.user?.displayName).toBe('Alice Smith');
    expect(state.user?.avatarUrl).toBe('https://example.com/avatar.png');
    expect(state.user?.appRole).toBe('STANDARD');
  });

  it('redirects to /login on fetch failure', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Network error'));

    renderCallback('?access_token=bad-token&provider=google');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        '/login?error=oauth_user_fetch_failed',
        { replace: true }
      );
    });
  });

  it('redirects to /login when /users/me returns non-ok', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Unauthorized' }),
    });

    renderCallback('?access_token=expired-token&provider=google');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith(
        '/login?error=oauth_user_fetch_failed',
        { replace: true }
      );
    });
  });

  it('shows loading spinner while processing', () => {
    mockFetch.mockReturnValue(new Promise(() => {})); // never resolves

    const { getByText } = renderCallback('?access_token=tok&provider=google');

    expect(getByText('Completing sign-in…')).toBeInTheDocument();
  });

  it('defaults appRole to STANDARD when not provided', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 'user-1',
        tenant_id: 'tenant-1',
        email: 'bob@example.com',
        given_name: 'Bob',
        family_name: null,
        avatar_url: null,
        email_verified: true,
      }),
    });

    renderCallback('?access_token=tok&provider=google');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true });
    });

    expect(useAuthStore.getState().user?.appRole).toBe('STANDARD');
  });

  it('uses email as displayName when names are empty', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        id: 'user-1',
        tenant_id: 'tenant-1',
        email: 'noname@example.com',
        given_name: null,
        family_name: null,
        avatar_url: null,
        email_verified: true,
        app_role: 'STANDARD',
      }),
    });

    renderCallback('?access_token=tok&provider=google');

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard', { replace: true });
    });

    expect(useAuthStore.getState().user?.displayName).toBe('noname@example.com');
  });
});
