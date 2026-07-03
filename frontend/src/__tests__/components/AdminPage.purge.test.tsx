/**
 * Unit tests for AdminPage's "Delete permanently" (hard-delete) flow.
 *
 * Covers:
 *  - Button visibility gating (Super Admin only, deactivated users only, never on self)
 *  - Confirmation modal content and cancel behaviour
 *  - Successful purge: correct request, list mutation, total decrement
 *  - Failed purge: error surfaced, user stays in the list
 */
import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { useAuthStore } from '@store/auth.store';
import AdminPage from '@pages/AdminPage';
import '../../i18n';

const API_BASE = '/api/v1';

const SUPER_ADMIN = {
  id: 'admin-1',
  tenantId: 'tenant-1',
  email: 'super@example.com',
  displayName: 'Super Admin',
  isEmailVerified: true,
  appRole: 'SUPER_ADMIN' as const,
};

const REGULAR_ADMIN = {
  ...SUPER_ADMIN,
  appRole: 'ADMIN' as const,
};

function makeUser(overrides: Partial<{
  id: string; email: string; given_name: string | null; family_name: string | null;
  app_role: 'SUPER_ADMIN' | 'ADMIN' | 'STANDARD' | 'AUDITOR';
  is_active: boolean; email_verified: boolean;
}> = {}) {
  return {
    id: 'user-1',
    email: 'target@example.com',
    given_name: 'Target',
    family_name: 'User',
    avatar_url: null,
    app_role: 'STANDARD' as const,
    email_verified: true,
    is_active: true,
    last_login_at: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function usersResponse(items: ReturnType<typeof makeUser>[]) {
  return {
    total: items.length,
    items,
    page: 1,
    page_size: 25,
    total_pages: 1,
  };
}

function renderAdminPage() {
  return render(
    <HelmetProvider>
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    </HelmetProvider>
  );
}

async function rowFor(email: string) {
  const cell = await screen.findByText(email);
  const row = cell.closest('tr');
  if (!row) throw new Error(`No <tr> ancestor found for ${email}`);
  return within(row);
}

describe('AdminPage — permanently delete user', () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    global.fetch = mockFetch;
    mockFetch.mockReset();
    useAuthStore.setState({
      accessToken: 'test-access-token',
      user: SUPER_ADMIN,
      isInitialised: true,
      isAuthenticated: true,
    });
  });

  // ── Button visibility gating ──────────────────────────────────────────────

  it('does not show the delete-forever button for an active user, even as Super Admin', async () => {
    const activeUser = makeUser({ id: 'user-active', email: 'active@example.com', is_active: true });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => usersResponse([activeUser]) });

    renderAdminPage();

    const row = await rowFor('active@example.com');
    expect(row.queryByText('Delete permanently')).not.toBeInTheDocument();
  });

  it('shows the delete-forever button for a deactivated user when logged in as Super Admin', async () => {
    const deactivatedUser = makeUser({ id: 'user-inactive', email: 'inactive@example.com', is_active: false });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => usersResponse([deactivatedUser]) });

    renderAdminPage();

    const row = await rowFor('inactive@example.com');
    expect(row.getByText('Delete permanently')).toBeInTheDocument();
  });

  it('does not show the delete-forever button for a deactivated user when logged in as a regular Admin', async () => {
    useAuthStore.setState({ user: REGULAR_ADMIN });
    const deactivatedUser = makeUser({ id: 'user-inactive', email: 'inactive@example.com', is_active: false });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => usersResponse([deactivatedUser]) });

    renderAdminPage();

    const row = await rowFor('inactive@example.com');
    expect(row.queryByText('Delete permanently')).not.toBeInTheDocument();
  });

  it('never shows the delete-forever button on the Super Admin\'s own (deactivated) row', async () => {
    const self = makeUser({
      id: SUPER_ADMIN.id, // same id as the logged-in user
      email: 'super@example.com',
      is_active: false,
    });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => usersResponse([self]) });

    renderAdminPage();

    const row = await rowFor('super@example.com');
    expect(row.queryByText('Delete permanently')).not.toBeInTheDocument();
  });

  // ── Confirmation modal ─────────────────────────────────────────────────────

  it('opens a confirmation dialog naming the user and does not call the API until confirmed', async () => {
    const user = userEvent.setup();
    const deactivatedUser = makeUser({ id: 'user-inactive', email: 'inactive@example.com', is_active: false });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => usersResponse([deactivatedUser]) });

    renderAdminPage();

    const row = await rowFor('inactive@example.com');
    await user.click(row.getByText('Delete permanently'));

    // Modal renders with a second, distinct "Delete permanently" confirm button
    const dialogHeading = await screen.findByRole('heading', { name: /delete permanently\?/i });
    expect(dialogHeading).toBeInTheDocument();
    const dialogCard = dialogHeading.closest('div')!;
    expect(within(dialogCard).getByText('Target User')).toBeInTheDocument(); // display name of the target
    expect(mockFetch).toHaveBeenCalledTimes(1); // only the initial list fetch so far
  });

  it('closes the confirmation dialog on Cancel without calling the API', async () => {
    const user = userEvent.setup();
    const deactivatedUser = makeUser({ id: 'user-inactive', email: 'inactive@example.com', is_active: false });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => usersResponse([deactivatedUser]) });

    renderAdminPage();

    const row = await rowFor('inactive@example.com');
    await user.click(row.getByText('Delete permanently'));
    await screen.findByRole('heading', { name: /delete permanently\?/i });

    await user.click(screen.getByText('Cancel'));

    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: /delete permanently\?/i })).not.toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  // ── Confirmed purge: success and failure paths ────────────────────────────

  it('sends DELETE /admin/users/{id}/purge with the bearer token and removes the user from the list on success', async () => {
    const user = userEvent.setup();
    const deactivatedUser = makeUser({ id: 'user-inactive', email: 'inactive@example.com', is_active: false });
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => usersResponse([deactivatedUser]) }) // initial list
      .mockResolvedValueOnce({ ok: true, status: 204 }); // purge call

    renderAdminPage();

    const row = await rowFor('inactive@example.com');
    await user.click(row.getByText('Delete permanently'));
    await screen.findByRole('heading', { name: /delete permanently\?/i });

    const dialog = screen.getByText(/delete permanently\?/i).closest('div')!.parentElement!;
    await user.click(within(dialog).getAllByText('Delete permanently').slice(-1)[0]);

    await waitFor(() => {
      expect(screen.queryByText('inactive@example.com')).not.toBeInTheDocument();
    });

    const purgeCall = mockFetch.mock.calls.find(([url]) => String(url).includes('/purge'));
    expect(purgeCall).toBeTruthy();
    const [url, options] = purgeCall!;
    expect(url).toBe(`${API_BASE}/admin/users/user-inactive/purge`);
    expect(options).toMatchObject({
      method: 'DELETE',
      credentials: 'include',
      headers: { Authorization: 'Bearer test-access-token' },
    });

    // "0 users total" — the removed row also decremented the visible total
    expect(await screen.findByText(/0 users total/i)).toBeInTheDocument();
  });

  it('shows an error and keeps the user listed when the backend rejects the purge (e.g. still active)', async () => {
    const user = userEvent.setup();
    const deactivatedUser = makeUser({ id: 'user-inactive', email: 'inactive@example.com', is_active: false });
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => usersResponse([deactivatedUser]) }) // initial list
      .mockResolvedValueOnce({ ok: false, status: 400, json: async () => ({ detail: 'User must be deactivated first' }) });

    renderAdminPage();

    const row = await rowFor('inactive@example.com');
    await user.click(row.getByText('Delete permanently'));
    await screen.findByRole('heading', { name: /delete permanently\?/i });

    const dialog = screen.getByText(/delete permanently\?/i).closest('div')!.parentElement!;
    await user.click(within(dialog).getAllByText('Delete permanently').slice(-1)[0]);

    expect(await screen.findByText('Failed to permanently delete user')).toBeInTheDocument();
    // User is still in the table — nothing was optimistically removed
    expect(screen.getByText('inactive@example.com')).toBeInTheDocument();
  });
});
