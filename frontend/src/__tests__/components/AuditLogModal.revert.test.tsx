/**
 * Component tests for AuditLogModal's admin-only "Revert" action on an
 * APPROVE_CHANGE entry.
 *
 * Covers:
 *  - Button visibility gating (Super Admin only)
 *  - Inline confirm/cancel flow — no API call until confirmed
 *  - Successful revert calls the right endpoint and refreshes the log
 *  - Failed revert surfaces the server's error message
 *  - A request that already shows a REVERT_CHANGE entry on the same page
 *    doesn't offer Revert again
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { useAuthStore } from '@store/auth.store';
import { AuditLogModal } from '@features/audit/AuditLogModal';
import '../../i18n';

const TREE_ID = 'tree-1';
const REQUEST_ID = 'change-request-1';

const SUPER_ADMIN_USER = {
  id: 'admin-1', tenantId: 'tenant-1', email: 'super@example.com',
  displayName: 'Super Admin', isEmailVerified: true, appRole: 'SUPER_ADMIN' as const,
};

const OWNER_USER = { ...SUPER_ADMIN_USER, id: 'owner-1', email: 'owner@example.com', appRole: 'STANDARD' as const };

function approveEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: 'audit-1',
    actor_display_name: 'Jane Editor',
    action: 'APPROVE_CHANGE',
    entity_type: 'CHANGE_REQUEST',
    entity_id: REQUEST_ID,
    entity_display_name: null,
    before: null,
    after: { added: 1, modified: 1, removed: 0 },
    occurred_at: new Date().toISOString(),
    ...overrides,
  };
}

const server = setupServer();

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function renderModal() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <AuditLogModal treeId={TREE_ID} onClose={() => {}} />
    </QueryClientProvider>,
  );
}

function mockAuditLog(entries: ReturnType<typeof approveEntry>[]) {
  server.use(
    http.get(`/api/v1/trees/${TREE_ID}/audit-log`, () => HttpResponse.json(entries)),
  );
}

describe('AuditLogModal — revert an approved change request', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: 'token', isInitialised: true, isAuthenticated: true });
  });

  it('shows the Revert button on an APPROVE_CHANGE entry for a Super Admin', async () => {
    useAuthStore.setState({ user: SUPER_ADMIN_USER });
    mockAuditLog([approveEntry()]);
    renderModal();

    expect(await screen.findByText('Revert')).toBeInTheDocument();
  });

  it('does not show the Revert button for a non-Super-Admin viewer', async () => {
    useAuthStore.setState({ user: OWNER_USER });
    mockAuditLog([approveEntry()]);
    renderModal();

    await screen.findByText('Approved proposal');
    expect(screen.queryByText('Revert')).not.toBeInTheDocument();
  });

  it('does not offer Revert for a request that already has a REVERT_CHANGE entry on this page', async () => {
    useAuthStore.setState({ user: SUPER_ADMIN_USER });
    mockAuditLog([
      approveEntry(),
      {
        id: 'audit-2', actor_display_name: 'Super Admin', action: 'REVERT_CHANGE',
        entity_type: 'CHANGE_REQUEST', entity_id: REQUEST_ID, entity_display_name: null,
        before: null, after: { restored_persons: 3, removed_persons: 1 },
        occurred_at: new Date().toISOString(),
      },
    ]);
    renderModal();

    await screen.findByText('Approved proposal');
    expect(screen.queryByText('Revert')).not.toBeInTheDocument();
  });

  it('does not call the API until the inline warning is confirmed', async () => {
    const user = userEvent.setup();
    useAuthStore.setState({ user: SUPER_ADMIN_USER });
    mockAuditLog([approveEntry()]);
    const revertHandler = vi.fn(() => HttpResponse.json({ id: REQUEST_ID, status: 'APPROVED', reverted: true }));
    server.use(
      http.post(`/api/v1/trees/${TREE_ID}/change-requests/${REQUEST_ID}/revert`, revertHandler),
    );
    renderModal();

    await user.click(await screen.findByText('Revert'));
    expect(await screen.findByText(/this cannot be undone/i)).toBeInTheDocument();
    expect(revertHandler).not.toHaveBeenCalled();

    await user.click(screen.getByText('Cancel'));
    await waitFor(() => {
      expect(screen.queryByText(/this cannot be undone/i)).not.toBeInTheDocument();
    });
    expect(revertHandler).not.toHaveBeenCalled();
  });

  it('reverts on confirm and refreshes the log to show the new REVERT_CHANGE entry', async () => {
    const user = userEvent.setup();
    useAuthStore.setState({ user: SUPER_ADMIN_USER });

    let reverted = false;
    server.use(
      http.get(`/api/v1/trees/${TREE_ID}/audit-log`, () =>
        HttpResponse.json(
          reverted
            ? [
                {
                  id: 'audit-2', actor_display_name: 'Super Admin', action: 'REVERT_CHANGE',
                  entity_type: 'CHANGE_REQUEST', entity_id: REQUEST_ID, entity_display_name: null,
                  before: null, after: null, occurred_at: new Date().toISOString(),
                },
                approveEntry(),
              ]
            : [approveEntry()],
        ),
      ),
      http.post(`/api/v1/trees/${TREE_ID}/change-requests/${REQUEST_ID}/revert`, () => {
        reverted = true;
        return HttpResponse.json({ id: REQUEST_ID, status: 'APPROVED', reverted: true });
      }),
    );
    renderModal();

    await user.click(await screen.findByText('Revert'));
    await user.click(await screen.findByText('Yes, revert'));

    expect(await screen.findByText('Reverted approved proposal')).toBeInTheDocument();
    // The now-reverted approval no longer offers a Revert button.
    expect(screen.queryByText('Revert')).not.toBeInTheDocument();
  });

  it('shows the server error and keeps the confirm panel open on failure', async () => {
    const user = userEvent.setup();
    useAuthStore.setState({ user: SUPER_ADMIN_USER });
    mockAuditLog([approveEntry()]);
    server.use(
      http.post(`/api/v1/trees/${TREE_ID}/change-requests/${REQUEST_ID}/revert`, () =>
        HttpResponse.json({ detail: 'This change request has already been reverted' }, { status: 409 }),
      ),
    );
    renderModal();

    await user.click(await screen.findByText('Revert'));
    await user.click(await screen.findByText('Yes, revert'));

    expect(await screen.findByText('This change request has already been reverted')).toBeInTheDocument();
    // Still offering the confirm buttons — nothing silently closed.
    expect(screen.getByText('Yes, revert')).toBeInTheDocument();
  });
});
