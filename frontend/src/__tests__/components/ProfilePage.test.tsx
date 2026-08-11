/**
 * Component tests for ProfilePage.
 *
 * Covers:
 *  - Shows "Back to tree" and links to the tree by default
 *  - Shows "Back to results" and links back to the search URL when navigated
 *    here from search results (location.state.from === 'search')
 *  - Shows a clickable tree-name link (when the tree's graph has loaded)
 *    that navigates to the tree with this person focused via ?focusPerson=
 *  - Renders no tree-name link when the tree name isn't available yet
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { HelmetProvider } from 'react-helmet-async';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ProfilePage from '@pages/ProfilePage';
import { queryKeys } from '@queries/keys';
import '../../i18n';

vi.mock('@store/auth.store', () => {
  const mockFn: any = vi.fn((selector: any) => selector({ accessToken: 'fake-token' }));
  mockFn.getState = vi.fn(() => ({ accessToken: 'fake-token' }));
  return { useAuthStore: mockFn };
});

const TREE_ID = 'tree-1';
const PERSON_ID = 'person-1';

const PERSON = {
  id: PERSON_ID,
  tree_id: TREE_ID,
  display_given_name: 'Ada',
  display_surname: 'Lovelace',
  sex: 'FEMALE',
  is_living: false,
  is_deceased: true,
  photo_url: null,
  parents: [],
  children: [],
  spouses: [],
  siblings: [],
};

function renderProfilePage({
  treeName,
  locationState,
}: {
  treeName?: string;
  locationState?: Record<string, unknown>;
} = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  qc.setQueryData(queryKeys.persons.detail(TREE_ID, PERSON_ID), PERSON);
  qc.setQueryData(queryKeys.trees.detail(TREE_ID), {
    treeId: TREE_ID,
    treeName,
    persons: [],
    familyGroups: [],
  });

  const entry = {
    pathname: `/trees/${TREE_ID}/persons/${PERSON_ID}`,
    state: locationState,
  };

  return render(
    <HelmetProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route path="/trees/:treeId/persons/:personId" element={<ProfilePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </HelmetProvider>
  );
}

describe('ProfilePage', () => {
  it('shows "Back to tree" linking to the tree by default', async () => {
    renderProfilePage({ treeName: 'Lovelace Family' });
    const back = await screen.findByRole('link', { name: /back to tree/i });
    expect(back).toHaveAttribute('href', `/trees/${TREE_ID}`);
  });

  it('shows "Back to results" linking to the search URL when arriving from search', async () => {
    renderProfilePage({
      treeName: 'Lovelace Family',
      locationState: { from: 'search', searchUrl: '/search?q=ada' },
    });
    const back = await screen.findByRole('link', { name: /back to results/i });
    expect(back).toHaveAttribute('href', '/search?q=ada');
  });

  it('shows a clickable tree-name link that focuses this person in the tree', async () => {
    renderProfilePage({ treeName: 'Lovelace Family' });
    const treeLink = await screen.findByRole('link', { name: /Lovelace Family/i });
    expect(treeLink).toHaveAttribute('href', `/trees/${TREE_ID}?focusPerson=${PERSON_ID}`);
  });

  it('renders no tree-name link when the tree name is not yet available', async () => {
    renderProfilePage({ treeName: undefined });
    await screen.findByText('Ada Lovelace');
    expect(screen.queryByRole('link', { name: /focusPerson/i })).not.toBeInTheDocument();
    const links = screen.getAllByRole('link');
    expect(links.every((l) => !l.getAttribute('href')?.includes('focusPerson'))).toBe(true);
  });
});
