/**
 * Component tests for AddRelationshipModal.
 *
 * Covers:
 *  - Person-picker search/filter/select
 *  - Custom label field only shown (and required) for the Custom relationship type
 *  - Submit calls createRelationship with person1/person2 swapped correctly
 *    for a forward vs. a reverse direction option
 *  - onAdded fires on success; onClose fires on Cancel
 *  - Server error message is surfaced without closing the modal
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AddRelationshipModal } from '@features/tree/relationships/AddRelationshipModal';
import { createRelationship } from '@features/tree/relationships/api';
import type { ApiPerson } from '@features/tree/types';
import '../../i18n';

vi.mock('@features/tree/relationships/api', () => ({
  createRelationship: vi.fn(),
}));

const mockCreateRelationship = vi.mocked(createRelationship);

function person(id: string, givenName: string): ApiPerson {
  return {
    id,
    treeId: 'tree-1',
    displayGivenName: givenName,
    displaySurname: 'Smith',
    sex: 'UNKNOWN',
    isLiving: true,
    isDeceased: false,
  };
}

const CANDIDATES: ApiPerson[] = [person('bob', 'Bob'), person('carol', 'Carol')];

function renderModal(overrides: Partial<React.ComponentProps<typeof AddRelationshipModal>> = {}) {
  const onClose = vi.fn();
  const onAdded = vi.fn();
  const utils = render(
    <AddRelationshipModal
      treeId="tree-1"
      anchorPersonId="alice"
      anchorName="Alice Smith"
      candidates={CANDIDATES}
      onClose={onClose}
      onAdded={onAdded}
      {...overrides}
    />,
  );
  return { ...utils, onClose, onAdded };
}

describe('AddRelationshipModal', () => {
  beforeEach(() => {
    mockCreateRelationship.mockReset();
  });

  it('filters candidates by the search input', async () => {
    const user = userEvent.setup();
    renderModal();
    expect(screen.getByText('Bob Smith')).toBeInTheDocument();
    expect(screen.getByText('Carol Smith')).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('Search by name…'), 'Bob');
    expect(screen.getByText('Bob Smith')).toBeInTheDocument();
    expect(screen.queryByText('Carol Smith')).not.toBeInTheDocument();
  });

  it('does not show a custom-label field for a non-Custom relationship type', () => {
    renderModal();
    expect(screen.queryByPlaceholderText('e.g. Business Partner')).not.toBeInTheDocument();
  });

  it('shows a custom-label field when Custom relationship is selected', async () => {
    const user = userEvent.setup();
    renderModal();
    await user.selectOptions(screen.getByLabelText('Relationship'), 'Custom relationship');
    expect(screen.getByPlaceholderText('e.g. Business Partner')).toBeInTheDocument();
  });

  it('submits with the anchor as person1 for a forward direction (Godparent of)', async () => {
    const user = userEvent.setup();
    mockCreateRelationship.mockResolvedValue({
      id: 'rel-1', person1_id: 'alice', person2_id: 'bob',
      relationship_type: 'GODPARENT', custom_label: null, notes: null, created_at: '2026-01-01',
    });
    const { onAdded } = renderModal();

    await user.click(screen.getByText('Bob Smith'));
    await user.click(screen.getByRole('button', { name: 'Add relationship' }));

    await waitFor(() => expect(mockCreateRelationship).toHaveBeenCalledWith('tree-1', {
      person1_id: 'alice',
      person2_id: 'bob',
      relationship_type: 'GODPARENT',
      custom_label: null,
      notes: null,
    }));
    expect(onAdded).toHaveBeenCalledTimes(1);
  });

  it('submits with the anchor as person2 for a reverse direction (Godchild of)', async () => {
    const user = userEvent.setup();
    mockCreateRelationship.mockResolvedValue({
      id: 'rel-1', person1_id: 'bob', person2_id: 'alice',
      relationship_type: 'GODPARENT', custom_label: null, notes: null, created_at: '2026-01-01',
    });
    renderModal();

    await user.selectOptions(screen.getByLabelText('Relationship'), 'Godchild of');
    await user.click(screen.getByText('Bob Smith'));
    await user.click(screen.getByRole('button', { name: 'Add relationship' }));

    await waitFor(() => expect(mockCreateRelationship).toHaveBeenCalledWith('tree-1', {
      person1_id: 'bob',
      person2_id: 'alice',
      relationship_type: 'GODPARENT',
      custom_label: null,
      notes: null,
    }));
  });

  it('requires a custom label before submitting a Custom relationship', async () => {
    const user = userEvent.setup();
    renderModal();

    await user.selectOptions(screen.getByLabelText('Relationship'), 'Custom relationship');
    await user.click(screen.getByText('Bob Smith'));
    await user.click(screen.getByRole('button', { name: 'Add relationship' }));

    expect(await screen.findByText('Enter a label for this custom relationship')).toBeInTheDocument();
    expect(mockCreateRelationship).not.toHaveBeenCalled();
  });

  it('submits the custom label when provided', async () => {
    const user = userEvent.setup();
    mockCreateRelationship.mockResolvedValue({
      id: 'rel-1', person1_id: 'alice', person2_id: 'bob',
      relationship_type: 'CUSTOM', custom_label: 'Business Partner', notes: null, created_at: '2026-01-01',
    });
    renderModal();

    await user.selectOptions(screen.getByLabelText('Relationship'), 'Custom relationship');
    await user.type(screen.getByPlaceholderText('e.g. Business Partner'), 'Business Partner');
    await user.click(screen.getByText('Bob Smith'));
    await user.click(screen.getByRole('button', { name: 'Add relationship' }));

    await waitFor(() => expect(mockCreateRelationship).toHaveBeenCalledWith('tree-1', expect.objectContaining({
      relationship_type: 'CUSTOM',
      custom_label: 'Business Partner',
    })));
  });

  it('calls onClose when Cancel is clicked', async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal();
    await user.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('shows the server error message and keeps the modal open on failure', async () => {
    const user = userEvent.setup();
    mockCreateRelationship.mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: 'This relationship already exists' } },
    });
    const { onAdded } = renderModal();

    await user.click(screen.getByText('Bob Smith'));
    await user.click(screen.getByRole('button', { name: 'Add relationship' }));

    expect(await screen.findByText('This relationship already exists')).toBeInTheDocument();
    expect(onAdded).not.toHaveBeenCalled();
  });
});
