/**
 * Unit tests for TreeCanvas's applyDiffStatusMap — the overlay that colors
 * added/modified persons on the canvas during change-request review.
 */
import { applyDiffStatusMap } from '@features/tree/canvas/TreeCanvas';

type Node = { id: string; type: string; data: Record<string, unknown> };

function personNode(id: string): Node {
  return { id, type: 'person', data: { personId: id, displayGivenName: id } };
}

function familyGroupNode(id: string): Node {
  return { id, type: 'family-group', data: { familyGroupId: id } };
}

describe('applyDiffStatusMap', () => {
  it('returns the same array reference when there is no diff map (normal browsing)', () => {
    const nodes = [personNode('p1'), personNode('p2')];
    const result = applyDiffStatusMap(nodes as any, undefined);
    expect(result).toBe(nodes);
  });

  it('tags a matching person node with its diff status', () => {
    const nodes = [personNode('p1'), personNode('p2')];
    const result = applyDiffStatusMap(nodes as any, { p1: 'added' });
    expect(result[0].data.diffStatus).toBe('added');
    expect(result[1].data.diffStatus).toBeUndefined();
  });

  it('leaves nodes with no entry in the map untouched (same reference)', () => {
    const nodes = [personNode('p1'), personNode('p2')];
    const result = applyDiffStatusMap(nodes as any, { p1: 'added' });
    expect(result[1]).toBe(nodes[1]);
  });

  it('does not tag family-group nodes even if their id collides with the map', () => {
    const nodes = [familyGroupNode('shared-id')];
    const result = applyDiffStatusMap(nodes as any, { 'shared-id': 'added' });
    expect(result[0].data.diffStatus).toBeUndefined();
  });

  it('supports both added and modified in the same pass', () => {
    const nodes = [personNode('p1'), personNode('p2'), personNode('p3')];
    const result = applyDiffStatusMap(nodes as any, { p1: 'added', p2: 'modified' });
    expect(result.map((n) => n.data.diffStatus)).toEqual(['added', 'modified', undefined]);
  });

  it('preserves the rest of each node untouched when tagging', () => {
    const nodes = [personNode('p1')];
    const result = applyDiffStatusMap(nodes as any, { p1: 'modified' });
    expect(result[0].id).toBe('p1');
    expect(result[0].type).toBe('person');
    expect(result[0].data.displayGivenName).toBe('p1');
  });
});
