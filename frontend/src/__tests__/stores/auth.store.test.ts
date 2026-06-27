/**
 * Unit tests for the auth Zustand store.
 * Tests state transitions: login, logout, token refresh.
 */
import { act, renderHook } from '@testing-library/react';
import { useAuthStore, initAuth } from '@store/auth.store';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset store to initial state
    useAuthStore.setState({
      accessToken: null,
      user: null,
      isInitialised: false,
    });
    mockFetch.mockReset();
  });

  describe('login', () => {
    it('stores access token in memory (not localStorage)', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.login('test-token-abc', {
          id: 'user-1',
          tenantId: 'tenant-1',
          email: 'alice@test.com',
          displayName: 'Alice Smith',
          avatarUrl: undefined,
          isEmailVerified: true,
          appRole: 'STANDARD',
        });
      });

      expect(result.current.accessToken).toBe('test-token-abc');
      expect(result.current.user?.email).toBe('alice@test.com');
      // Critical: must NOT be in localStorage
      expect(localStorage.getItem('access_token')).toBeNull();
    });

    it('sets user fields correctly', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.login('tok', {
          id: 'u1',
          tenantId: 't1',
          email: 'bob@test.com',
          displayName: 'Bob Jones',
          avatarUrl: 'https://example.com/avatar.png',
          isEmailVerified: false,
          appRole: 'STANDARD',
        });
      });

      expect(result.current.user?.displayName).toBe('Bob Jones');
      expect(result.current.user?.avatarUrl).toBe('https://example.com/avatar.png');
      expect(result.current.user?.isEmailVerified).toBe(false);
    });
  });

  describe('logout', () => {
    it('clears access token and user', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.login('some-token', {
          id: 'u1', tenantId: 't1', email: 'test@test.com',
          displayName: 'Test', avatarUrl: undefined, isEmailVerified: true, appRole: 'STANDARD',
        });
      });

      act(() => {
        result.current.logout();
      });

      expect(result.current.accessToken).toBeNull();
      expect(result.current.user).toBeNull();
    });
  });

  describe('initAuth', () => {
    it('calls /api/v1/auth/refresh on init', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'refreshed-token',
          user: {
            id: 'u1',
            tenant_id: 't1',
            email: 'alice@test.com',
            display_given_name: 'Alice',
            display_surname: 'Smith',
            avatar_url: null,
            is_email_verified: true,
          },
        }),
      });

      await act(async () => {
        await initAuth();
      });

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/auth/refresh',
        expect.objectContaining({ method: 'POST', credentials: 'include' })
      );

      const state = useAuthStore.getState();
      expect(state.accessToken).toBe('refreshed-token');
      expect(state.isInitialised).toBe(true);
    });

    it('sets isInitialised=true even if refresh fails', async () => {
      mockFetch.mockResolvedValueOnce({ ok: false });

      await act(async () => {
        await initAuth();
      });

      expect(useAuthStore.getState().isInitialised).toBe(true);
      expect(useAuthStore.getState().accessToken).toBeNull();
    });

    it('handles network error gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      await act(async () => {
        await initAuth();
      });

      expect(useAuthStore.getState().isInitialised).toBe(true);
    });
  });

  describe('isAuthenticated selector', () => {
    it('returns false when no token', () => {
      const state = useAuthStore.getState();
      expect(!!state.accessToken).toBe(false);
    });

    it('returns true after login', () => {
      act(() => {
        useAuthStore.getState().login('tok', {
          id: 'u', tenantId: 't', email: 'e@e.com',
          displayName: 'E', avatarUrl: undefined, isEmailVerified: true, appRole: 'STANDARD',
        });
      });
      expect(!!useAuthStore.getState().accessToken).toBe(true);
    });
  });

  describe('OAuth callback login', () => {
    it('stores OAuth token and user from callback', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.login('oauth-jwt-token', {
          id: 'oauth-user-1',
          tenantId: 'oauth-tenant-1',
          email: 'oauth@google.com',
          displayName: 'OAuth User',
          avatarUrl: 'https://lh3.google.com/avatar',
          isEmailVerified: true,
          appRole: 'STANDARD',
        });
      });

      expect(result.current.accessToken).toBe('oauth-jwt-token');
      expect(result.current.user?.email).toBe('oauth@google.com');
      expect(result.current.user?.avatarUrl).toBe('https://lh3.google.com/avatar');
      expect(result.current.isAuthenticated).toBe(true);
    });

    it('handles OAuth user with ADMIN role', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.login('admin-token', {
          id: 'admin-1',
          tenantId: 't1',
          email: 'admin@example.com',
          displayName: 'Admin User',
          avatarUrl: undefined,
          isEmailVerified: true,
          appRole: 'ADMIN',
        });
      });

      expect(result.current.user?.appRole).toBe('ADMIN');
    });

    it('logout clears OAuth session', () => {
      const { result } = renderHook(() => useAuthStore());

      act(() => {
        result.current.login('oauth-token', {
          id: 'u1', tenantId: 't1', email: 'o@g.com',
          displayName: 'O', avatarUrl: 'https://avatar.url', isEmailVerified: true, appRole: 'STANDARD',
        });
      });

      act(() => {
        result.current.logout();
      });

      expect(result.current.accessToken).toBeNull();
      expect(result.current.user).toBeNull();
      expect(result.current.isAuthenticated).toBe(false);
    });
  });

  describe('initAuth with OAuth session', () => {
    it('recovers OAuth session via silent refresh', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ access_token: 'refreshed-oauth-token' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            id: 'oauth-user',
            tenant_id: 'tenant-1',
            email: 'oauth@google.com',
            given_name: 'OAuth',
            family_name: 'User',
            avatar_url: 'https://lh3.google.com/pic',
            email_verified: true,
            app_role: 'STANDARD',
          }),
        });

      await act(async () => {
        await initAuth();
      });

      const state = useAuthStore.getState();
      expect(state.accessToken).toBe('refreshed-oauth-token');
      expect(state.isInitialised).toBe(true);
    });
  });
});
