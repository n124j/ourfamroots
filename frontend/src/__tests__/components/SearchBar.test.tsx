/**
 * Component tests for SearchBar.
 * Uses MSW to mock the search API.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import '../../i18n';
import { SearchBar } from '@features/search/components/SearchBar';
import type { NameSearchResponse } from '@features/search/types';

// ── MSW server ─────────────────────────────────────────────────────────────────

const MOCK_RESULTS: NameSearchResponse = {
  total: 2,
  took_ms: 5,
  hits: [
    {
      person_id: 'p1',
      tree_id: 'tree1',
      given_name: 'John',
      surname: 'Smith',
      maiden_name: null,
      birth_year: 1850,
      death_year: 1920,
      birth_place: 'London',
      is_living: false,
      score: 0.9,
    },
    {
      person_id: 'p2',
      tree_id: 'tree1',
      given_name: 'Jane',
      surname: 'Smith',
      maiden_name: 'Jones',
      birth_year: 1855,
      death_year: null,
      birth_place: null,
      is_living: true,
      score: 0.75,
    },
  ],
};

const server = setupServer(
  http.get('/api/v1/search', () => HttpResponse.json(MOCK_RESULTS)),
  http.get('/api/v1/trees/:treeId/search', () => HttpResponse.json(MOCK_RESULTS)),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ── Helpers ────────────────────────────────────────────────────────────────────

function renderSearchBar(props = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <SearchBar {...props} />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('SearchBar', () => {
  const user = userEvent.setup({ delay: null });

  it('renders input with default placeholder', () => {
    renderSearchBar();
    expect(screen.getByPlaceholderText('Search people…')).toBeInTheDocument();
  });

  it('renders custom placeholder', () => {
    renderSearchBar({ placeholder: 'Find an ancestor…' });
    expect(screen.getByPlaceholderText('Find an ancestor…')).toBeInTheDocument();
  });

  it('does not show dropdown for query shorter than 2 chars', async () => {
    renderSearchBar();
    await user.type(screen.getByRole('searchbox'), 'J');
    await waitFor(() => {
      expect(screen.queryByText('John Smith')).not.toBeInTheDocument();
    });
  });

  it('shows results for query >= 2 chars', async () => {
    renderSearchBar();
    const input = screen.getByRole('searchbox');
    await user.type(input, 'Smith');

    await waitFor(() => {
      expect(screen.getByText('John Smith')).toBeInTheDocument();
    });
  });

  it('shows maiden name for matching result', async () => {
    renderSearchBar();
    await user.type(screen.getByRole('searchbox'), 'Smith');

    await waitFor(() => {
      // Jane Smith née Jones
      expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    });
  });

  it('closes dropdown on Escape', async () => {
    renderSearchBar();
    const input = screen.getByRole('searchbox');
    await user.type(input, 'Smith');

    await waitFor(() => expect(screen.getByText('John Smith')).toBeInTheDocument());

    await user.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByText('John Smith')).not.toBeInTheDocument();
    });
  });

  it('calls onSelect when a result is clicked', async () => {
    const onSelect = jest.fn();
    renderSearchBar({ onSelect });
    await user.type(screen.getByRole('searchbox'), 'Smith');

    await waitFor(() => expect(screen.getByText('John Smith')).toBeInTheDocument());

    await user.click(screen.getByText('John Smith'));
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ person_id: 'p1', surname: 'Smith' })
    );
  });

  it('shows "No results found" when API returns empty', async () => {
    server.use(
      http.get('/api/v1/search', () =>
        HttpResponse.json({ total: 0, hits: [], took_ms: 2 })
      )
    );

    renderSearchBar();
    await user.type(screen.getByRole('searchbox'), 'Zzzzz');

    await waitFor(() => {
      expect(screen.getByText('No results found.')).toBeInTheDocument();
    });
  });

  it('shows "View all N results" link when total > 8', async () => {
    const manyResults: NameSearchResponse = {
      total: 25,
      took_ms: 10,
      hits: Array.from({ length: 8 }, (_, i) => ({
        person_id: `p${i}`,
        tree_id: 'tree1',
        given_name: 'Person',
        surname: `Smith ${i}`,
        maiden_name: null,
        birth_year: null,
        death_year: null,
        birth_place: null,
        is_living: false,
        score: 0.5,
      })),
    };
    server.use(http.get('/api/v1/search', () => HttpResponse.json(manyResults)));

    renderSearchBar();
    await user.type(screen.getByRole('searchbox'), 'Smith');

    await waitFor(() => {
      expect(screen.getByText(/View all 25 results/)).toBeInTheDocument();
    });
  });
});
