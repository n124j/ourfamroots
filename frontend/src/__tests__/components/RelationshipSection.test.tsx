/**
 * Component tests for RelationshipSection — the "Other Relationships"
 * (Godparent/Guardian/Mentor/Custom) block shown on a person's profile.
 *
 * Covers:
 *  - Forward vs. reverse reciprocal label rendering (Godparent of / Godchild of, etc.)
 *  - Custom relationship shows its custom_label
 *  - Only relationships involving the current person are shown
 *  - "+ Add relationship" and remove (×) buttons are canWrite-gated
 *  - Remove button calls onRemove with the relationship id
 *  - Empty state when there are no relationships
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RelationshipSection } from '@features/tree/relationships/RelationshipSection';
import type { ApiPerson, ApiRelationship } from '@features/tree/types';
import '../../i18n';

const ALICE_ID = 'alice';
const BOB_ID = 'bob';
const CAROL_ID = 'carol';

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

const PERSON_MAP: Record<string, ApiPerson> = {
  [ALICE_ID]: person(ALICE_ID, 'Alice'),
  [BOB_ID]: person(BOB_ID, 'Bob'),
  [CAROL_ID]: person(CAROL_ID, 'Carol'),
};

const NAME_MAP: Record<string, string> = {
  [ALICE_ID]: 'Alice Smith',
  [BOB_ID]: 'Bob Smith',
  [CAROL_ID]: 'Carol Smith',
};

function relationship(overrides: Partial<ApiRelationship> = {}): ApiRelationship {
  return {
    id: 'rel-1',
    person1_id: ALICE_ID,
    person2_id: BOB_ID,
    relationship_type: 'GODPARENT',
    custom_label: null,
    notes: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

function noop() {}

function renderSection(props: Partial<React.ComponentProps<typeof RelationshipSection>> = {}) {
  return render(
    <RelationshipSection
      personId={ALICE_ID}
      relationships={[relationship()]}
      personMap={PERSON_MAP}
      nameMap={NAME_MAP}
      canWrite={true}
      onNavigate={noop}
      onAdd={noop}
      onRemove={noop}
      {...props}
    />,
  );
}

describe('RelationshipSection', () => {
  it('shows the forward label when the viewer is person1 (the role holder)', () => {
    renderSection({
      personId: ALICE_ID,
      relationships: [relationship({ person1_id: ALICE_ID, person2_id: BOB_ID, relationship_type: 'GODPARENT' })],
    });
    expect(screen.getByText('Godparent of')).toBeInTheDocument();
    expect(screen.getByText('Bob Smith')).toBeInTheDocument();
  });

  it('shows the reverse label when the viewer is person2', () => {
    renderSection({
      personId: BOB_ID,
      relationships: [relationship({ person1_id: ALICE_ID, person2_id: BOB_ID, relationship_type: 'GODPARENT' })],
    });
    expect(screen.getByText('Godchild of')).toBeInTheDocument();
    expect(screen.getByText('Alice Smith')).toBeInTheDocument();
  });

  it.each([
    ['GUARDIAN', 'Guardian of', 'Ward of'],
    ['MENTOR', 'Mentor of', 'Mentee of'],
  ] as const)('renders %s forward/reverse labels correctly', (type, forwardLabel, reverseLabel) => {
    renderSection({
      personId: ALICE_ID,
      relationships: [relationship({ person1_id: ALICE_ID, person2_id: BOB_ID, relationship_type: type })],
    });
    expect(screen.getByText(forwardLabel)).toBeInTheDocument();

    renderSection({
      personId: BOB_ID,
      relationships: [relationship({ person1_id: ALICE_ID, person2_id: BOB_ID, relationship_type: type })],
    });
    expect(screen.getByText(reverseLabel)).toBeInTheDocument();
  });

  it('shows the custom_label for a CUSTOM relationship regardless of direction', () => {
    renderSection({
      personId: ALICE_ID,
      relationships: [relationship({ relationship_type: 'CUSTOM', custom_label: 'Business Partner' })],
    });
    expect(screen.getByText('Business Partner')).toBeInTheDocument();
  });

  it('only shows relationships involving the current person', () => {
    renderSection({
      personId: ALICE_ID,
      relationships: [
        relationship({ id: 'rel-1', person1_id: ALICE_ID, person2_id: BOB_ID }),
        relationship({ id: 'rel-2', person1_id: BOB_ID, person2_id: CAROL_ID }),
      ],
    });
    expect(screen.getByText('Bob Smith')).toBeInTheDocument();
    expect(screen.queryByText('Carol Smith')).not.toBeInTheDocument();
  });

  it('shows the empty state when there are no relationships for this person', () => {
    renderSection({ personId: ALICE_ID, relationships: [] });
    expect(screen.getByText('No other relationships recorded yet.')).toBeInTheDocument();
  });

  it('shows "+ Add relationship" and calls onAdd when clicked, only if canWrite', async () => {
    const user = userEvent.setup();
    const onAdd = vi.fn();
    renderSection({ canWrite: true, onAdd });
    const addButton = screen.getByText(/Add relationship/);
    await user.click(addButton);
    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it('hides "+ Add relationship" and remove buttons when canWrite is false', () => {
    renderSection({ canWrite: false });
    expect(screen.queryByText(/Add relationship/)).not.toBeInTheDocument();
    expect(screen.queryByTitle('Remove relationship')).not.toBeInTheDocument();
  });

  it('calls onRemove with the relationship id when the remove button is clicked', async () => {
    const user = userEvent.setup();
    const onRemove = vi.fn();
    renderSection({
      canWrite: true,
      relationships: [relationship({ id: 'rel-42' })],
      onRemove,
    });
    await user.click(screen.getByTitle('Remove relationship'));
    expect(onRemove).toHaveBeenCalledWith('rel-42');
  });

  it('calls onNavigate with the other person\'s id when a row is clicked', async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderSection({
      personId: ALICE_ID,
      relationships: [relationship({ person1_id: ALICE_ID, person2_id: BOB_ID })],
      onNavigate,
    });
    await user.click(screen.getByText('Bob Smith'));
    expect(onNavigate).toHaveBeenCalledWith(BOB_ID);
  });
});
