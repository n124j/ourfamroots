/**
 * Unit tests for AdminPage's Broadcast Email panel — the async-queueing
 * behavior specifically (POST /broadcast/send now returns a queued marker
 * instead of final counts, and the History list polls itself while a
 * broadcast is still sending).
 */
import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
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

function usersResponse() {
  return { total: 0, items: [], page: 1, page_size: 25, total_pages: 1 };
}

function historyResponse(items: any[]) {
  return { total: items.length, items };
}

function historyItem(overrides: Partial<{
  id: string; sent_count: number; failed_count: number; recipient_count: number; in_progress: boolean;
}> = {}) {
  return {
    id: 'log-1',
    sender_display_name: 'Super Admin',
    subject: 'Hello',
    body: 'World',
    category: 'notice',
    recipient_count: 1,
    sent_count: 0,
    failed_count: 0,
    in_progress: true,
    recipient_emails: ['user@example.com'],
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
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

async function goToBroadcastTab(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByText('Broadcast'));
}

describe('AdminPage — Broadcast email (async queueing)', () => {
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

  it('shows a "queued" confirmation with the recipient count, not final sent/failed counts', async () => {
    const user = userEvent.setup();
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => usersResponse() }) // initial users list
      .mockResolvedValueOnce({ ok: true, json: async () => historyResponse([]) }) // broadcast history on tab mount
      .mockResolvedValueOnce({ ok: true, json: async () => ({ log_id: 'log-99', recipient_count: 5 }) }) // POST /broadcast/send
      .mockResolvedValueOnce({ ok: true, json: async () => historyResponse([historyItem({ id: 'log-99', recipient_count: 5 })]) }); // loadHistory() after send

    renderAdminPage();
    await goToBroadcastTab(user);
    await screen.findByText('No broadcasts sent yet.');

    await user.type(screen.getByPlaceholderText(/scheduled maintenance/i), 'Hello');
    await user.type(screen.getByPlaceholderText(/write your message here/i), 'World');
    await user.click(screen.getByText('Send broadcast'));

    expect(await screen.findByText(/Queued — sending to 5 recipients/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Sent to/i)).not.toBeInTheDocument();

    const sendCall = mockFetch.mock.calls.find(([url]) => String(url).includes('/broadcast/send'));
    expect(sendCall).toBeTruthy();
    const [, options] = sendCall!;
    expect(JSON.parse(options.body)).toMatchObject({ subject: 'Hello', body: 'World', category: 'notice', recipient_ids: [] });
  });

  it('shows "Sending…" for an in-progress broadcast and polls until it completes', async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ delay: null });
    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => usersResponse() }) // initial users list
      .mockResolvedValueOnce({ ok: true, json: async () => historyResponse([historyItem({ in_progress: true })]) }) // initial history
      .mockResolvedValueOnce({ // polled refresh — now complete
        ok: true,
        json: async () => historyResponse([historyItem({ in_progress: false, sent_count: 1, failed_count: 0 })]),
      });

    renderAdminPage();
    await goToBroadcastTab(user);

    expect(await screen.findByText('Sending…')).toBeInTheDocument();

    const historyCallsBefore = mockFetch.mock.calls.filter(([url]) => String(url).includes('/broadcast/history')).length;
    expect(historyCallsBefore).toBe(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });

    await waitFor(() => {
      expect(screen.getByText('1 sent')).toBeInTheDocument();
    });
    expect(screen.queryByText('Sending…')).not.toBeInTheDocument();

    // Completed — no further polling should occur even after another interval tick.
    const historyCallsAfter = mockFetch.mock.calls.filter(([url]) => String(url).includes('/broadcast/history')).length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(mockFetch.mock.calls.filter(([url]) => String(url).includes('/broadcast/history')).length).toBe(historyCallsAfter);

    vi.useRealTimers();
  });
});
