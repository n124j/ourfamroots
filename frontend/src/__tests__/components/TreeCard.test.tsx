/**
 * Component tests for the Dashboard's per-tree card (`TreeCard`, exported
 * from `pages/DashboardPage.tsx`).
 *
 * Covers:
 *  - "Hide from Dashboard" is rendered on every tree card, global or not
 *    (previously gated behind `tree.is_globally_shared`).
 *  - The member-count badge is suppressed on a globally-shared tree's card
 *    (membership there is managed via the global permission group) but
 *    still shown on a regular tree's card.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { TreeCard, type TreeSummary } from '@pages/DashboardPage';
import '../../i18n';

function noop() {}

function tree(overrides: Partial<TreeSummary> = {}): TreeSummary {
  return {
    id: 'tree-1',
    name: 'The Test Family',
    description: null,
    cover_emoji: null,
    cover_image_url: null,
    role: 'OWNER',
    person_count: 42,
    member_count: 3,
    link_sharing: 'OFF',
    share_token: null,
    is_pinned: false,
    is_searchable: false,
    is_globally_shared: false,
    ...overrides,
  };
}

function renderCard(overrides: Partial<TreeSummary> = {}, handlers: Partial<Record<'onHide' | 'onTogglePin', () => void>> = {}) {
  return render(
    <MemoryRouter>
      <TreeCard
        tree={tree(overrides)}
        onEdit={noop}
        onDelete={noop}
        onShare={noop}
        onTogglePin={handlers.onTogglePin ?? noop}
        onHide={handlers.onHide ?? noop}
      />
    </MemoryRouter>,
  );
}

describe('TreeCard', () => {
  it('shows the "Hide from Dashboard" icon on a regular (non-global) tree', () => {
    renderCard({ is_globally_shared: false });
    expect(screen.getByTitle('Hide from Dashboard')).toBeInTheDocument();
  });

  it('shows the "Hide from Dashboard" icon on a globally-shared tree', () => {
    renderCard({ is_globally_shared: true });
    expect(screen.getByTitle('Hide from Dashboard')).toBeInTheDocument();
  });

  it('calls onHide with the tree when the hide icon is clicked', async () => {
    const user = userEvent.setup();
    const onHide = vi.fn();
    renderCard({ is_globally_shared: false, id: 'tree-42' }, { onHide });

    await user.click(screen.getByTitle('Hide from Dashboard'));
    expect(onHide).toHaveBeenCalledTimes(1);
    expect(onHide.mock.calls[0][0].id).toBe('tree-42');
  });

  it('hides the member-count badge on a globally-shared tree, but still shows person count', () => {
    renderCard({ is_globally_shared: true, person_count: 87, member_count: 5 });

    expect(screen.getByText('87')).toBeInTheDocument();
    expect(screen.queryByText('5')).not.toBeInTheDocument();
    expect(screen.queryByText(/member/)).not.toBeInTheDocument();
  });

  it('still shows the member-count badge on a regular (non-global) tree', () => {
    renderCard({ is_globally_shared: false, person_count: 48, member_count: 1 });

    expect(screen.getByText('48')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('member')).toBeInTheDocument();
  });

  it('shows the full tree name as a tooltip (title attribute), for when it is truncated', () => {
    const longName = 'The Extraordinarily Long Multi-Generational Family Dynasty Tree';
    renderCard({ name: longName });

    expect(screen.getByText(longName)).toHaveAttribute('title', longName);
  });

  it('shows the full description as a tooltip (title attribute), for when it is clamped', () => {
    const longDescription = 'A very long description that spans well beyond two lines and would otherwise be clipped by line-clamp-2 without a way to read the rest of it.';
    renderCard({ description: longDescription });

    expect(screen.getByText(longDescription)).toHaveAttribute('title', longDescription);
  });

  it('renders no description tooltip element when the tree has no description', () => {
    renderCard({ description: null });

    // The <p> element for description is conditionally rendered entirely.
    const card = screen.getByText('The Test Family').closest('.group');
    expect(card?.querySelector('p[title]')).not.toBeInTheDocument();
  });
});
