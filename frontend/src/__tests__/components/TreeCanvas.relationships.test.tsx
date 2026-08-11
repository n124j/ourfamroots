/**
 * Unit tests for buildRelationshipEdges — the "Other Relationships"
 * (Godparent/Guardian/Mentor/Custom) canvas overlay.
 *
 * This function is the regression guard for the core design constraint:
 * relationship edges are a pure post-layout visual overlay and must never
 * be fed into dagre/the layout algorithms (see TreeCanvas.tsx's header
 * comment on buildRelationshipEdges). Testing it in isolation — the same
 * pattern already used for applyDiffStatusMap (TreeCanvas.diff.test.tsx) —
 * proves the "both endpoints visible" contract without mounting the full
 * ReactFlow/dagre canvas.
 */
import { buildRelationshipEdges } from '@features/tree/canvas/TreeCanvas';
import type { ApiRelationship } from '@features/tree/types';

function relationship(overrides: Partial<ApiRelationship> = {}): ApiRelationship {
  return {
    id: 'rel-1',
    person1_id: 'alice',
    person2_id: 'bob',
    relationship_type: 'GODPARENT',
    custom_label: null,
    notes: null,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

const label = (rel: ApiRelationship) => `label-for-${rel.relationship_type}`;

describe('buildRelationshipEdges', () => {
  it('returns an empty array when relationships is undefined', () => {
    expect(buildRelationshipEdges(undefined, new Set(['alice', 'bob']), label)).toEqual([]);
  });

  it('returns an empty array when relationships is empty', () => {
    expect(buildRelationshipEdges([], new Set(['alice', 'bob']), label)).toEqual([]);
  });

  it('builds one edge per relationship when both endpoints are visible', () => {
    const rels = [relationship()];
    const edges = buildRelationshipEdges(rels, new Set(['alice', 'bob']), label);
    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({
      id: 'rel-rel-1',
      type: 'relationship',
      source: 'alice',
      target: 'bob',
      data: { kind: 'relationship', relationshipType: 'GODPARENT', label: 'label-for-GODPARENT' },
    });
  });

  it('excludes a relationship when person1 is not currently visible', () => {
    const rels = [relationship({ person1_id: 'alice', person2_id: 'bob' })];
    const edges = buildRelationshipEdges(rels, new Set(['bob']), label);
    expect(edges).toHaveLength(0);
  });

  it('excludes a relationship when person2 is not currently visible', () => {
    const rels = [relationship({ person1_id: 'alice', person2_id: 'bob' })];
    const edges = buildRelationshipEdges(rels, new Set(['alice']), label);
    expect(edges).toHaveLength(0);
  });

  it('excludes a relationship when neither endpoint is visible', () => {
    const rels = [relationship({ person1_id: 'alice', person2_id: 'bob' })];
    const edges = buildRelationshipEdges(rels, new Set(['carol']), label);
    expect(edges).toHaveLength(0);
  });

  it('only includes the subset whose both endpoints are visible, out of many', () => {
    const rels = [
      relationship({ id: 'r1', person1_id: 'alice', person2_id: 'bob' }),      // both visible
      relationship({ id: 'r2', person1_id: 'carol', person2_id: 'dave' }),     // neither visible
      relationship({ id: 'r3', person1_id: 'alice', person2_id: 'eve' }),      // eve not visible
    ];
    const edges = buildRelationshipEdges(rels, new Set(['alice', 'bob']), label);
    expect(edges.map((e) => e.id)).toEqual(['rel-r1']);
  });

  it('uses a namespaced edge id ("rel-" prefix) to avoid colliding with union/parent-child edge ids', () => {
    const rels = [relationship({ id: 'abc-123' })];
    const edges = buildRelationshipEdges(rels, new Set(['alice', 'bob']), label);
    expect(edges[0].id).toBe('rel-abc-123');
  });

  it('every returned edge has type "relationship" so it renders via the RelationshipEdge component', () => {
    const rels = [relationship(), relationship({ id: 'rel-2', relationship_type: 'GUARDIAN' })];
    const edges = buildRelationshipEdges(rels, new Set(['alice', 'bob']), label);
    expect(edges.every((e) => e.type === 'relationship')).toBe(true);
  });
});
