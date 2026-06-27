/**
 * Unit tests for PermissionGuard and isPermitted() helper.
 */
import React from 'react';
import { vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PermissionGuard, isPermitted, ROLE_HIERARCHY, ACTION_MIN_ROLE } from '@shared/components/PermissionGuard';
import { queryKeys } from '@queries/keys';

// ── isPermitted() pure function ────────────────────────────────────────────────

describe('isPermitted()', () => {
  it('owner is permitted for all actions', () => {
    for (const action of Object.keys(ACTION_MIN_ROLE)) {
      expect(isPermitted('OWNER', action)).toBe(true);
    }
  });

  it('viewer can view but not create', () => {
    expect(isPermitted('VIEWER', 'VIEW_PERSON')).toBe(true);
    expect(isPermitted('VIEWER', 'CREATE_PERSON')).toBe(false);
  });

  it('editor can create but not invite', () => {
    expect(isPermitted('EDITOR', 'CREATE_PERSON')).toBe(true);
    expect(isPermitted('EDITOR', 'INVITE_MEMBER')).toBe(false);
  });

  it('admin can invite but not delete tree', () => {
    expect(isPermitted('ADMIN', 'INVITE_MEMBER')).toBe(true);
    expect(isPermitted('ADMIN', 'DELETE_TREE')).toBe(false);
  });

  it('returns false for unknown action', () => {
    expect(isPermitted('OWNER', 'UNKNOWN_ACTION')).toBe(false);
  });
});

// ── Role hierarchy monotonicity ────────────────────────────────────────────────

describe('ROLE_HIERARCHY', () => {
  it('owner > admin > editor > viewer', () => {
    expect(ROLE_HIERARCHY['OWNER']).toBeGreaterThan(ROLE_HIERARCHY['ADMIN']);
    expect(ROLE_HIERARCHY['ADMIN']).toBeGreaterThan(ROLE_HIERARCHY['EDITOR']);
    expect(ROLE_HIERARCHY['EDITOR']).toBeGreaterThan(ROLE_HIERARCHY['VIEWER']);
  });
});

// ── PermissionGuard component ──────────────────────────────────────────────────

// useTreeRole reads userId from useAuthStore; mock it to return a known user.
const TEST_USER_ID = 'test-user-123';

vi.mock('@store/auth.store', () => {
  const mockFn: any = vi.fn((selector: any) =>
    selector({ user: { id: TEST_USER_ID }, accessToken: 'fake-token' })
  );
  mockFn.getState = vi.fn(() => ({ accessToken: 'fake-token' }));
  return { useAuthStore: mockFn };
});

/**
 * Renders `ui` inside a QueryClientProvider pre-seeded so that
 * useTreeRole returns the given role for treeId='tree-1'.
 * Passing role=null seeds an empty members list → user not found → role null.
 */
function renderWithRole(role: string | null, ui: React.ReactElement, treeId = 'tree-1') {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const members = role !== null ? [{ userId: TEST_USER_ID, role }] : [];
  qc.setQueryData(queryKeys.trees.members(treeId), members);
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('PermissionGuard', () => {
  afterEach(() => vi.clearAllMocks());

  it('renders children when user has sufficient role', () => {
    renderWithRole('EDITOR',
      <PermissionGuard action="CREATE_PERSON" treeId="tree-1">
        <button>Add Person</button>
      </PermissionGuard>
    );
    expect(screen.getByRole('button', { name: 'Add Person' })).toBeInTheDocument();
  });

  it('does not render children when role is insufficient', () => {
    renderWithRole('VIEWER',
      <PermissionGuard action="DELETE_TREE" treeId="tree-1">
        <button>Delete Tree</button>
      </PermissionGuard>
    );
    expect(screen.queryByRole('button', { name: 'Delete Tree' })).not.toBeInTheDocument();
  });

  it('renders fallback when role is insufficient', () => {
    renderWithRole('VIEWER',
      <PermissionGuard
        action="CREATE_PERSON"
        treeId="tree-1"
        fallback={<span>No permission</span>}
      >
        <button>Add</button>
      </PermissionGuard>
    );
    expect(screen.getByText('No permission')).toBeInTheDocument();
    expect(screen.queryByText('Add')).not.toBeInTheDocument();
  });

  it('renders nothing (not fallback) when no role available', () => {
    renderWithRole(null,
      <PermissionGuard action="VIEW_PERSON" treeId="tree-1">
        <span>Content</span>
      </PermissionGuard>
    );
    expect(screen.queryByText('Content')).not.toBeInTheDocument();
  });

  it('renders children for owner on destructive actions', () => {
    renderWithRole('OWNER',
      <PermissionGuard action="DELETE_TREE" treeId="tree-1">
        <button>Delete</button>
      </PermissionGuard>
    );
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });
});
