/**
 * Component tests for the Family Tree Poster's couple mode.
 *
 * When the focus person has a recorded spouse, the poster centres on the
 * couple and gives each of them their OWN full ancestor fan — one tree
 * branching left from the focus person, one tree branching right from their
 * spouse — rather than splitting a single person's two parents across both
 * halves. Uses a small "Byanjankar family" fixture (Niraj + Samita, each
 * with their own parents) to pin down this exact shape.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { ApiTreeGraph, ApiPerson, ApiFamilyGroup } from '@features/tree/types';
import { useCanvasStore } from '@store/canvas.store';
import { PosterPedigreeView } from '../../extensions/views/poster/PosterPedigreeView';

function person(id: string, given: string, surname: string, sex: 'MALE' | 'FEMALE'): ApiPerson {
  return {
    id, treeId: 't1', displayGivenName: given, displaySurname: surname, sex,
    isLiving: false, isDeceased: true,
  };
}

/** Parent-child link. */
function fg(id: string, parentIds: string[], childId: string): ApiFamilyGroup {
  return { id, treeId: 't1', unionType: 'MARRIAGE', parentIds, children: { [childId]: 'BIOLOGICAL' } };
}

/** Spouse-only union — no children recorded under it. */
function union(id: string, parentIds: string[]): ApiFamilyGroup {
  return { id, treeId: 't1', unionType: 'MARRIAGE', parentIds, children: {} };
}

const persons: ApiPerson[] = [
  person('niraj', 'Niraj', 'Byanjankar', 'MALE'),
  person('samita', 'Samita', 'Byanjankar', 'FEMALE'),
  person('nirajFather', 'Ram', 'Byanjankar', 'MALE'),
  person('nirajMother', 'Sita', 'Byanjankar', 'FEMALE'),
  person('samitaFather', 'Hari', 'Shrestha', 'MALE'),
  person('samitaMother', 'Gita', 'Shrestha', 'FEMALE'),
];

const familyGroups: ApiFamilyGroup[] = [
  union('marriage', ['niraj', 'samita']),
  fg('fg-niraj', ['nirajFather', 'nirajMother'], 'niraj'),
  fg('fg-samita', ['samitaFather', 'samitaMother'], 'samita'),
];

const graph: ApiTreeGraph = { treeId: 't1', persons, familyGroups };

// A second fixture, with three recorded children under the couple's union,
// to exercise the "kids' first names in a box below the couple" feature.
function familyGroupWithChildren(childIds: string[]): ApiFamilyGroup {
  return {
    id: 'marriage', treeId: 't1', unionType: 'MARRIAGE', parentIds: ['niraj', 'samita'],
    children: Object.fromEntries(childIds.map((id) => [id, 'BIOLOGICAL'])),
  };
}

const kids: ApiPerson[] = [
  person('owen', 'Owen', 'Byanjankar', 'MALE'),
  person('april', 'April', 'Byanjankar', 'FEMALE'),
  person('neeva', 'Neeva', 'Byanjankar', 'FEMALE'),
];
const graphWithChildren: ApiTreeGraph = {
  treeId: 't1',
  persons: [...persons, ...kids],
  familyGroups: [
    familyGroupWithChildren(['owen', 'april', 'neeva']),
    fg('fg-niraj', ['nirajFather', 'nirajMother'], 'niraj'),
    fg('fg-samita', ['samitaFather', 'samitaMother'], 'samita'),
  ],
};

beforeEach(() => {
  useCanvasStore.getState().reset();
  useCanvasStore.getState().setFocusPersonId('niraj');
});

describe('PosterPedigreeView — couple mode', () => {
  it('centres the poster on the couple, naming both in the header', () => {
    render(<PosterPedigreeView graph={graph} />);
    expect(screen.getByText("Niraj Byanjankar & Samita Byanjankar's Family Tree")).toBeInTheDocument();
  });

  it('renders both the focus person and their spouse as bottom-row boxes', () => {
    render(<PosterPedigreeView graph={graph} />);
    expect(screen.getByText('Niraj Byanjankar')).toBeInTheDocument();
    expect(screen.getByText('Samita Byanjankar')).toBeInTheDocument();
  });

  it("shows the focus person's own parents (not the couple's combined parents)", () => {
    render(<PosterPedigreeView graph={graph} />);
    expect(screen.getByText('Ram Byanjankar')).toBeInTheDocument();
    expect(screen.getByText('Sita Byanjankar')).toBeInTheDocument();
  });

  it("shows the spouse's own parents as a separate tree", () => {
    render(<PosterPedigreeView graph={graph} />);
    expect(screen.getByText('Hari Shrestha')).toBeInTheDocument();
    expect(screen.getByText('Gita Shrestha')).toBeInTheDocument();
  });

  it("positions the focus person's tree to the left and the spouse's tree to the right", () => {
    const { container } = render(<PosterPedigreeView graph={graph} />);
    const textOf = (label: string) =>
      Array.from(container.querySelectorAll('text')).find((t) => t.textContent === label);

    const nirajBox = textOf('Niraj Byanjankar');
    const samitaBox = textOf('Samita Byanjankar');
    expect(nirajBox && samitaBox).toBeTruthy();

    const x = (el: Element) => parseFloat(el.getAttribute('x') || '0');
    // Niraj sits left-of-centre, Samita right-of-centre, next to each other.
    expect(x(nirajBox!)).toBeLessThan(x(samitaBox!));
  });

  it("anchors each person's whole fan to their OWN box (not the couple's shared midpoint)", () => {
    const { container } = render(<PosterPedigreeView graph={graph} />);
    const textOf = (label: string) =>
      Array.from(container.querySelectorAll('text')).find((t) => t.textContent === label);
    const x = (el: Element) => parseFloat(el.getAttribute('x') || '0');

    const nirajBox = textOf('Niraj Byanjankar');
    const nirajFather = textOf('Ram Byanjankar');
    const nirajMother = textOf('Sita Byanjankar');
    expect(nirajBox && nirajFather && nirajMother).toBeTruthy();
    // Both of Niraj's own parents sit further left than Niraj himself — his
    // whole branch radiates outward from his own box, one direction only,
    // so it can never cross into (or collide with) Samita's branch.
    expect(x(nirajFather!)).toBeLessThan(x(nirajBox!));
    expect(x(nirajMother!)).toBeLessThan(x(nirajBox!));
    // The nearer parent sits close to Niraj's own box, not off near the
    // couple's shared midpoint (which is what the earlier, buggy
    // centreX-anchored version did) — well within one generation's own
    // box-and-gap width of him.
    const nirajNearestParentX = Math.max(x(nirajFather!), x(nirajMother!));
    expect(x(nirajBox!) - nirajNearestParentX).toBeLessThan(250); // one box-width-ish, not hundreds of px off toward centre

    const samitaBox = textOf('Samita Byanjankar');
    const samitaFather = textOf('Hari Shrestha');
    const samitaMother = textOf('Gita Shrestha');
    expect(samitaBox && samitaFather && samitaMother).toBeTruthy();
    expect(x(samitaFather!)).toBeGreaterThan(x(samitaBox!));
    expect(x(samitaMother!)).toBeGreaterThan(x(samitaBox!));
  });

  it('leaves ancestor boxes blank (not "Unknown") when no data is recorded beyond what exists', () => {
    render(<PosterPedigreeView graph={graph} />); // only 1 generation of ancestors recorded
    // Default view shows 4 generations — generations 2-4 are entirely unrecorded
    // and must render as empty boxes, not a wall of "Unknown" placeholders.
    expect(screen.queryByText('Unknown')).not.toBeInTheDocument();
  });

  it('never truncates names — the full first + middle + last name always renders', () => {
    const longName: ApiPerson[] = [
      person('niraj', 'Niraj Kumar Prasad', 'Byanjankar Shrestha', 'MALE'),
      person('samita', 'Samita', 'Byanjankar', 'FEMALE'),
    ];
    const g: ApiTreeGraph = { treeId: 't1', persons: longName, familyGroups: [union('marriage', ['niraj', 'samita'])] };
    render(<PosterPedigreeView graph={g} />);
    expect(screen.getByText('Niraj Kumar Prasad Byanjankar Shrestha')).toBeInTheDocument();
  });

  it("shows the couple's children as first names in a box below them, with no spouse-tree data", () => {
    render(<PosterPedigreeView graph={graphWithChildren} />);
    expect(screen.getByText('Owen, April, and Neeva')).toBeInTheDocument();
  });

  it('places the children box below the couple, connected by a line', () => {
    const { container } = render(<PosterPedigreeView graph={graphWithChildren} />);
    const textOf = (label: string) =>
      Array.from(container.querySelectorAll('text')).find((t) => t.textContent === label);
    const y = (el: Element) => parseFloat(el.getAttribute('y') || '0');

    const nirajBox = textOf('Niraj Byanjankar');
    const childrenBox = textOf('Owen, April, and Neeva');
    expect(nirajBox && childrenBox).toBeTruthy();
    // SVG y grows downward, so the children's row must be BELOW the couple's row.
    expect(y(childrenBox!)).toBeGreaterThan(y(nirajBox!));
  });

  it('omits the children box entirely when the couple has no recorded children', () => {
    render(<PosterPedigreeView graph={graph} />);
    expect(screen.queryByText(/Owen/)).not.toBeInTheDocument();
  });
});
