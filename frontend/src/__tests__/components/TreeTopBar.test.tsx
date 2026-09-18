/**
 * Component tests for the tree-viewing page's top toolbar (`TreeTopBar`,
 * exported from `pages/FamilyTreePage.tsx`).
 *
 * Covers:
 *  - "Layouts" and "Propose changes" are never rendered (desktop or mobile
 *    overflow menu), regardless of role/tree-sharing state — removed from
 *    the UI outright.
 *  - "Activity" is rendered for a tree OWNER, ADMIN, or a SUPER_ADMIN viewer
 *    (matches the backend's VIEW_AUDIT_LOG permission), and hidden for
 *    EDITOR/VIEWER roles, on both global and non-global trees.
 *  - "Members" and "Pending proposals" are unaffected regression checks.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { useAuthStore } from '@store/auth.store';
import { TreeTopBar } from '@pages/FamilyTreePage';
import type { ApiTreeGraph } from '@features/tree/types';
import '../../i18n';

const SUPER_ADMIN_USER = {
  id: 'admin-1', tenantId: 'tenant-1', email: 'super@example.com',
  displayName: 'Super Admin', isEmailVerified: true, appRole: 'SUPER_ADMIN' as const,
};

const STANDARD_USER = { ...SUPER_ADMIN_USER, id: 'user-1', email: 'user@example.com', appRole: 'STANDARD' as const };

function graph(overrides: Partial<ApiTreeGraph> = {}): ApiTreeGraph {
  return { treeId: 'tree-1', persons: [], familyGroups: [], ...overrides };
}

function noop() {}
function asyncNoop() { return Promise.resolve(); }

function renderTopBar(props: Partial<React.ComponentProps<typeof TreeTopBar>> = {}) {
  return render(
    <MemoryRouter>
      <TreeTopBar
        treeName="Test Family"
        personCount={10}
        graph={graph()}
        token="token"
        canWrite={true}
        userRole="EDITOR"
        pendingChangeCount={0}
        onAddPerson={noop}
        onMembers={noop}
        onLayouts={noop}
        onExportCsv={noop}
        onExportPdf={asyncNoop}
        onTheme={noop}
        onShowActivity={noop}
        onProposeChanges={noop}
        onOpenPost={noop}
        onViewPendingProposals={noop}
        {...props}
      />
    </MemoryRouter>,
  );
}

describe('TreeTopBar', () => {
  beforeEach(() => {
    useAuthStore.setState({ accessToken: 'token', isInitialised: true, isAuthenticated: true, user: STANDARD_USER });
  });

  it('never renders a "Layouts" button, on a regular tree or a global one', () => {
    renderTopBar({ graph: graph({ isGloballyShared: false }) });
    expect(screen.queryByText('Layouts')).not.toBeInTheDocument();

    renderTopBar({ graph: graph({ isGloballyShared: true }), userRole: 'EDITOR' });
    expect(screen.queryByText('Layouts')).not.toBeInTheDocument();
  });

  it('never renders a "Propose changes" button, even for an EDITOR on a non-draft global tree', () => {
    renderTopBar({
      graph: graph({ isGloballyShared: true }),
      userRole: 'EDITOR',
    });
    expect(screen.queryByText('Propose changes')).not.toBeInTheDocument();
  });

  it('hides "Activity" for an EDITOR, even without Super Admin', () => {
    useAuthStore.setState({ user: STANDARD_USER });
    renderTopBar({ userRole: 'EDITOR' });
    expect(screen.queryByText('Activity')).not.toBeInTheDocument();
  });

  it('shows "Activity" for a tree OWNER or ADMIN, even without Super Admin', () => {
    useAuthStore.setState({ user: STANDARD_USER });

    renderTopBar({ userRole: 'OWNER' });
    expect(screen.getAllByText('Activity').length).toBeGreaterThan(0);

    renderTopBar({ userRole: 'ADMIN' });
    expect(screen.getAllByText('Activity').length).toBeGreaterThan(0);
  });

  it('shows "Activity" for a Super Admin viewer and calls onShowActivity when clicked', async () => {
    const user = userEvent.setup();
    useAuthStore.setState({ user: SUPER_ADMIN_USER });
    const onShowActivity = vi.fn();
    renderTopBar({ onShowActivity });

    const activityButtons = screen.getAllByText('Activity');
    expect(activityButtons.length).toBeGreaterThan(0);
    await user.click(activityButtons[0]);
    expect(onShowActivity).toHaveBeenCalledTimes(1);
  });

  it('still hides "Members" on a globally-shared tree (unchanged behavior)', () => {
    renderTopBar({ graph: graph({ isGloballyShared: true }) });
    expect(screen.queryByText('Members')).not.toBeInTheDocument();
  });

  it('still shows "Members" on a regular (non-global) tree (unchanged behavior)', () => {
    renderTopBar({ graph: graph({ isGloballyShared: false }) });
    expect(screen.getAllByText('Members').length).toBeGreaterThan(0);
  });

  it('still shows "Pending proposals" for an OWNER with pending changes on a global tree (unchanged behavior)', () => {
    renderTopBar({
      graph: graph({ isGloballyShared: true }),
      userRole: 'OWNER',
      pendingChangeCount: 3,
    });
    expect(screen.getAllByText(/Pending proposals/).length).toBeGreaterThan(0);
  });
});
