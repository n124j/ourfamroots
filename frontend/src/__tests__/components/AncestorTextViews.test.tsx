/**
 * Component tests for the Text Pedigree and Family Tree Poster extension views.
 *
 * Uses the Lavinia Mitchell ancestry (4 generations) as fixture data — the same
 * family used to spec these views — to confirm both render the full connected
 * ancestor chain from real graph data, not just placeholder markup.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { ApiTreeGraph, ApiPerson, ApiFamilyGroup } from '@features/tree/types';
import { useCanvasStore } from '@store/canvas.store';
import { TextPedigreeView } from '../../extensions/views/text-pedigree/TextPedigreeView';
import { PosterPedigreeView } from '../../extensions/views/poster/PosterPedigreeView';

function person(id: string, given: string, surname: string, sex: 'MALE' | 'FEMALE'): ApiPerson {
  return {
    id, treeId: 't1', displayGivenName: given, displaySurname: surname, sex,
    isLiving: false, isDeceased: true,
  };
}

function fg(id: string, parentIds: string[], childId: string): ApiFamilyGroup {
  return { id, treeId: 't1', unionType: 'MARRIAGE', parentIds, children: { [childId]: 'BIOLOGICAL' } };
}

const persons: ApiPerson[] = [
  person('lavinia', 'Lavinia', 'Mitchell', 'FEMALE'),
  person('alfred', 'Alfred Hezekiah', 'Mitchell', 'MALE'),
  person('beatrice', 'Beatrice', 'Carlisle', 'FEMALE'),
  person('frederick', 'Frederick Augustus Herman Frank', 'Mitchell', 'MALE'),
  person('margaretT', 'Margaret', 'Thompson', 'FEMALE'),
  person('johnG', 'John George', 'Carlisle', 'MALE'),
  person('margaretK', 'Margaret Adeline', 'Kewley', 'FEMALE'),
  person('hezekiah', 'Hezekiah', 'Mitchell', 'MALE'),
  person('sarah', 'Sarah', 'Mallinson', 'FEMALE'),
  person('ralph', 'Ralph', 'Thompson', 'MALE'),
  person('ann1', 'Ann', 'Bentley', 'FEMALE'),
  person('johnC', 'John', 'Carlill', 'MALE'),
  person('mary', 'Mary', 'Shannon', 'FEMALE'),
  person('james', 'James', 'Kewley', 'MALE'),
  person('ann2', 'Ann', 'Karran', 'FEMALE'),
];

const familyGroups: ApiFamilyGroup[] = [
  fg('fg1', ['alfred', 'beatrice'], 'lavinia'),
  fg('fg2', ['frederick', 'margaretT'], 'alfred'),
  fg('fg3', ['johnG', 'margaretK'], 'beatrice'),
  fg('fg4', ['hezekiah', 'sarah'], 'frederick'),
  fg('fg5', ['ralph', 'ann1'], 'margaretT'),
  fg('fg6', ['johnC', 'mary'], 'johnG'),
  fg('fg7', ['james', 'ann2'], 'margaretK'),
];

const graph: ApiTreeGraph = { treeId: 't1', persons, familyGroups };

beforeEach(() => {
  useCanvasStore.getState().reset();
  useCanvasStore.getState().setFocusPersonId('lavinia');
});

describe('TextPedigreeView', () => {
  it('renders the root person and all four visible generations by default', () => {
    render(<TextPedigreeView graph={graph} />);
    expect(screen.getByText('Lavinia Mitchell')).toBeInTheDocument();
    expect(screen.getByText('Alfred Hezekiah Mitchell')).toBeInTheDocument();
    expect(screen.getByText('Beatrice Carlisle')).toBeInTheDocument();
    expect(screen.getByText('Frederick Augustus Herman Frank Mitchell')).toBeInTheDocument();
    expect(screen.getByText('Margaret Thompson')).toBeInTheDocument();
    expect(screen.getByText('Hezekiah Mitchell')).toBeInTheDocument();
    expect(screen.getByText('Sarah Mallinson')).toBeInTheDocument();
    expect(screen.getByText('Ralph Thompson')).toBeInTheDocument();
    expect(screen.getByText('Ann Bentley')).toBeInTheDocument();
    expect(screen.getByText('John George Carlisle')).toBeInTheDocument();
    expect(screen.getByText('Margaret Adeline Kewley')).toBeInTheDocument();
    expect(screen.getByText('John Carlill')).toBeInTheDocument();
    expect(screen.getByText('Mary Shannon')).toBeInTheDocument();
    expect(screen.getByText('James Kewley')).toBeInTheDocument();
    expect(screen.getByText('Ann Karran')).toBeInTheDocument();
  });

  it('shows the breadcrumb header naming the current root', () => {
    render(<TextPedigreeView graph={graph} />);
    expect(screen.getByText('Ancestors of Lavinia Mitchell')).toBeInTheDocument();
  });

  it('double-clicking a name re-roots the tree on that person via the canvas store', () => {
    render(<TextPedigreeView graph={graph} />);
    fireEvent.doubleClick(screen.getByText('Alfred Hezekiah Mitchell'));
    expect(useCanvasStore.getState().focusPersonId).toBe('alfred');
  });

  it('shows a Back button after double-clicking to re-root, which returns to the previous root', () => {
    render(<TextPedigreeView graph={graph} />);
    expect(screen.queryByText('← Back')).not.toBeInTheDocument();

    fireEvent.doubleClick(screen.getByText('Alfred Hezekiah Mitchell'));
    expect(useCanvasStore.getState().focusPersonId).toBe('alfred');
    expect(screen.getByText('← Back')).toBeInTheDocument();

    fireEvent.click(screen.getByText('← Back'));
    expect(useCanvasStore.getState().focusPersonId).toBe('lavinia');
    expect(screen.queryByText('← Back')).not.toBeInTheDocument();
  });

  it('Back unwinds multiple re-roots one step at a time', () => {
    render(<TextPedigreeView graph={graph} />);
    fireEvent.doubleClick(screen.getByText('Alfred Hezekiah Mitchell'));
    fireEvent.doubleClick(screen.getByText('Frederick Augustus Herman Frank Mitchell'));
    expect(useCanvasStore.getState().focusPersonId).toBe('frederick');

    fireEvent.click(screen.getByText('← Back'));
    expect(useCanvasStore.getState().focusPersonId).toBe('alfred');

    fireEvent.click(screen.getByText('← Back'));
    expect(useCanvasStore.getState().focusPersonId).toBe('lavinia');
    expect(screen.queryByText('← Back')).not.toBeInTheDocument();
  });

  it('the generations stepper reduces visible depth when decremented', () => {
    render(<TextPedigreeView graph={graph} />);
    // Default depth (4) shows great-grandparents (depth 3). Stepping down to 2
    // stops recursion at depth-2 people (Frederick etc.), hiding their depth-3
    // parents (Hezekiah etc.) behind a ▶ expand affordance instead.
    const minusBtn = screen.getByTitle('Fewer generations');
    fireEvent.click(minusBtn); // 4 -> 3
    fireEvent.click(minusBtn); // 3 -> 2
    expect(screen.queryByText('Hezekiah Mitchell')).not.toBeInTheDocument();
    expect(screen.getByText('Frederick Augustus Herman Frank Mitchell')).toBeInTheDocument();
    expect(screen.getAllByTitle('Show parents').length).toBeGreaterThan(0);
  });
});

describe('PosterPedigreeView', () => {
  it('renders the decorative title and the root person centred at the bottom', () => {
    render(<PosterPedigreeView graph={graph} />);
    expect(screen.getByText('My Family Tree')).toBeInTheDocument();
    // Root appears in the SVG box; there may be a duplicate in the toolbar caption.
    expect(screen.getAllByText('Lavinia Mitchell').length).toBeGreaterThan(0);
  });

  it('fills known ancestor boxes with full (untruncated) names up to the default generation count', () => {
    render(<PosterPedigreeView graph={graph} />);
    // Full names always render in the box itself — long ones just shrink to fit.
    expect(screen.getByText('Alfred Hezekiah Mitchell')).toBeInTheDocument();
    expect(screen.getByText('Beatrice Carlisle')).toBeInTheDocument();
    expect(screen.getByText('Hezekiah Mitchell')).toBeInTheDocument();
    expect(screen.getByText('Ann Karran')).toBeInTheDocument();
  });

  it('the generations stepper increases the number of ancestor rows shown', () => {
    render(<PosterPedigreeView graph={graph} />);
    expect(screen.getByText('4')).toBeInTheDocument(); // default generation count label
    fireEvent.click(screen.getByTitle('More generations'));
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('shows a photo tooltip on hover, in addition to the always-visible box name', () => {
    render(<PosterPedigreeView graph={graph} />);
    const box = screen.getByText('Alfred Hezekiah Mitchell');
    expect(screen.getAllByText('Alfred Hezekiah Mitchell')).toHaveLength(1);
    fireEvent.mouseEnter(box.closest('g') as Element);
    // The tooltip duplicates the name alongside a photo/initial avatar.
    expect(screen.getAllByText('Alfred Hezekiah Mitchell')).toHaveLength(2);
    fireEvent.mouseLeave(box.closest('g') as Element);
    expect(screen.getAllByText('Alfred Hezekiah Mitchell')).toHaveLength(1);
  });
});
