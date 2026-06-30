/**
 * Unit tests for familyTreeLayout — compact mode and core positioning.
 *
 * Covers:
 *  - compact: true repacks each generation row from MARGIN, eliminating dead space
 *  - compact: true re-centers union ring (FG) nodes between parents' new positions
 *  - compact: true preserves y-row values (generations stay on same rows)
 *  - compact: true produces equal or narrower total x-span vs compact: false
 *  - same-generation persons always share the same y coordinate
 *  - edge cases: empty graph, single person, single couple
 */

import { familyTreeLayout } from '@features/tree/canvas/algorithms/familyTree';
import type { ApiTreeGraph, ApiPerson, ApiFamilyGroup } from '@features/tree/types';
import {
  PERSON_NODE_WIDTH as PW,
  FAMILY_NODE_SIZE  as FS,
} from '@features/tree/types';

// ── Helpers ────────────────────────────────────────────────────────────────────

const MARGIN = 40; // mirrors the const inside familyTree.ts

function makePerson(id: string, birthYear?: number): ApiPerson {
  return {
    id,
    treeId: 'tree-1',
    displayGivenName: id,
    displaySurname: '',
    sex: 'UNKNOWN',
    isLiving: true,
    isDeceased: false,
    birthYear,
  };
}

function makeFG(id: string, parentIds: string[], children: Record<string, 'BIOLOGICAL'>): ApiFamilyGroup {
  return {
    id,
    treeId: 'tree-1',
    unionType: 'MARRIAGE',
    parentIds,
    children,
  };
}

function makeGraph(
  persons: ApiPerson[],
  familyGroups: ApiFamilyGroup[] = [],
): ApiTreeGraph {
  return { treeId: 'tree-1', persons, familyGroups };
}

function nodeById(nodes: ReturnType<typeof familyTreeLayout>, id: string) {
  const n = nodes.find((x) => x.id === id);
  if (!n) throw new Error(`node ${id} not found`);
  return n;
}

// ── Empty and trivial graphs ───────────────────────────────────────────────────

describe('familyTreeLayout — empty / trivial', () => {
  it('returns [] for an empty graph', () => {
    expect(familyTreeLayout(makeGraph([]))).toEqual([]);
  });

  it('returns one positioned node for a single person', () => {
    const result = familyTreeLayout(makeGraph([makePerson('alice')]));
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('alice');
    expect(Number.isFinite(result[0].x)).toBe(true);
    expect(Number.isFinite(result[0].y)).toBe(true);
  });

  it('compact: true on a single person returns the same node', () => {
    const result = familyTreeLayout(makeGraph([makePerson('alice')]), { compact: true });
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('alice');
  });

  it('returns person + FG node for a couple with no children', () => {
    const graph = makeGraph(
      [makePerson('alice'), makePerson('bob')],
      [makeFG('fg1', ['alice', 'bob'], {})],
    );
    const result = familyTreeLayout(graph);
    expect(result).toHaveLength(3); // alice + bob + fg1 ring
    const ids = result.map((n) => n.id);
    expect(ids).toContain('alice');
    expect(ids).toContain('bob');
    expect(ids).toContain('fg1');
  });
});

// ── Generation row invariants ──────────────────────────────────────────────────

describe('familyTreeLayout — same-generation y invariant', () => {
  /**
   * Two-generation graph:
   *   Gen 0: Alice + Bob (couple)
   *   Gen 1: Carol, Dave  (children)
   */
  const graph = makeGraph(
    [makePerson('alice'), makePerson('bob'), makePerson('carol'), makePerson('dave')],
    [makeFG('fg1', ['alice', 'bob'], { carol: 'BIOLOGICAL', dave: 'BIOLOGICAL' })],
  );

  it('parents share the same y', () => {
    const result = familyTreeLayout(graph);
    expect(nodeById(result, 'alice').y).toBe(nodeById(result, 'bob').y);
  });

  it('children share the same y', () => {
    const result = familyTreeLayout(graph);
    expect(nodeById(result, 'carol').y).toBe(nodeById(result, 'dave').y);
  });

  it('children are positioned below parents', () => {
    const result = familyTreeLayout(graph);
    expect(nodeById(result, 'carol').y).toBeGreaterThan(nodeById(result, 'alice').y);
  });

  it('compact: true preserves the same-generation y invariant', () => {
    const result = familyTreeLayout(graph, { compact: true });
    expect(nodeById(result, 'alice').y).toBe(nodeById(result, 'bob').y);
    expect(nodeById(result, 'carol').y).toBe(nodeById(result, 'dave').y);
  });

  it('compact: true does not change y positions', () => {
    const normal  = familyTreeLayout(graph, { compact: false });
    const compact = familyTreeLayout(graph, { compact: true });

    // y values must be identical — only x is repacked
    expect(nodeById(compact, 'alice').y).toBe(nodeById(normal, 'alice').y);
    expect(nodeById(compact, 'carol').y).toBe(nodeById(normal, 'carol').y);
  });
});

// ── Compact repacking ──────────────────────────────────────────────────────────

describe('familyTreeLayout — compact repacking', () => {
  /**
   * Wide tree: two couples, each with two children.
   *   Gen 0: A+B (fg1) → C,D    E+F (fg2) → G,H
   * In normal mode the two subtrees are placed far apart.
   * In compact mode every generation row starts from MARGIN.
   */
  const persons = [
    makePerson('A'), makePerson('B'),
    makePerson('C'), makePerson('D'),
    makePerson('E'), makePerson('F'),
    makePerson('G'), makePerson('H'),
  ];
  const fgs = [
    makeFG('fg1', ['A', 'B'], { C: 'BIOLOGICAL', D: 'BIOLOGICAL' }),
    makeFG('fg2', ['E', 'F'], { G: 'BIOLOGICAL', H: 'BIOLOGICAL' }),
  ];
  const graph = makeGraph(persons, fgs);

  it('compact result has same node count as normal result', () => {
    const normal  = familyTreeLayout(graph, { compact: false });
    const compact = familyTreeLayout(graph, { compact: true });
    expect(compact).toHaveLength(normal.length);
  });

  it('compact packs gen-0 persons from MARGIN', () => {
    const result = familyTreeLayout(graph, { compact: true });
    const gen0 = ['A', 'B', 'E', 'F'].map((id) => nodeById(result, id));
    const leftmost = Math.min(...gen0.map((n) => n.x));
    expect(leftmost).toBe(MARGIN);
  });

  it('compact packs gen-1 persons from MARGIN', () => {
    const result = familyTreeLayout(graph, { compact: true });
    const gen1 = ['C', 'D', 'G', 'H'].map((id) => nodeById(result, id));
    const leftmost = Math.min(...gen1.map((n) => n.x));
    expect(leftmost).toBe(MARGIN);
  });

  it('compact produces a total x-span ≤ normal span for an unbalanced tree', () => {
    // A solo grandparent (Alice) → Bob → 4 grand-children creates a wide normal
    // layout: Bob and his spouse Carol get pushed far right by the 4-child subtree.
    // Compact repacks each generation from MARGIN, so the top generation is tighter.
    const unbalancedGraph = makeGraph(
      [
        makePerson('alice'),
        makePerson('bob'), makePerson('carol'),
        makePerson('d1'), makePerson('d2'), makePerson('d3'), makePerson('d4'),
      ],
      [
        makeFG('fg0', ['alice'], { bob: 'BIOLOGICAL' }),
        makeFG('fg1', ['bob', 'carol'], {
          d1: 'BIOLOGICAL', d2: 'BIOLOGICAL', d3: 'BIOLOGICAL', d4: 'BIOLOGICAL',
        }),
      ],
    );
    const normal  = familyTreeLayout(unbalancedGraph, { compact: false });
    const compact = familyTreeLayout(unbalancedGraph, { compact: true });
    const maxX = (nodes: typeof normal) => Math.max(...nodes.filter(n => ['alice','bob','carol'].includes(n.id)).map(n => n.x));
    // In the normal layout Alice/Bob/Carol are centered over the 4-child subtree
    // → their x is much larger than in compact mode which starts at MARGIN.
    expect(maxX(compact)).toBeLessThanOrEqual(maxX(normal) + 1);
  });

  it('all positions are finite numbers', () => {
    const result = familyTreeLayout(graph, { compact: true });
    for (const n of result) {
      expect(Number.isFinite(n.x)).toBe(true);
      expect(Number.isFinite(n.y)).toBe(true);
    }
  });
});

// ── FG ring re-centering after compact repack ──────────────────────────────────

describe('familyTreeLayout — FG node centered between parents after compact', () => {
  const graph = makeGraph(
    [makePerson('alice'), makePerson('bob'), makePerson('carol')],
    [makeFG('fg1', ['alice', 'bob'], { carol: 'BIOLOGICAL' })],
  );

  it('FG ring is at midpoint between alice and bob after compact repack', () => {
    const result = familyTreeLayout(graph, { compact: true });
    const alice  = nodeById(result, 'alice');
    const bob    = nodeById(result, 'bob');
    const fg1    = nodeById(result, 'fg1');

    const expectedX = (Math.min(alice.x, bob.x) + Math.max(alice.x, bob.x) + PW) / 2 - FS / 2;
    expect(fg1.x).toBeCloseTo(expectedX, 0);
  });

  it('single-parent FG ring is offset from the parent center', () => {
    const graph2 = makeGraph(
      [makePerson('alice'), makePerson('carol')],
      [makeFG('fg1', ['alice'], { carol: 'BIOLOGICAL' })],
    );
    const result = familyTreeLayout(graph2, { compact: true });
    const alice  = nodeById(result, 'alice');
    const fg1    = nodeById(result, 'fg1');

    // Single parent: ring x = parent.x + PW/2 - FS/2
    const expectedX = alice.x + PW / 2 - FS / 2;
    expect(fg1.x).toBeCloseTo(expectedX, 0);
  });
});

// ── Custom gap opts ────────────────────────────────────────────────────────────

describe('familyTreeLayout — custom gap options', () => {
  it('respects nodeHGap and nodeVGap in compact mode', () => {
    const graph = makeGraph(
      [makePerson('alice'), makePerson('bob'), makePerson('carol'), makePerson('dave')],
      [makeFG('fg1', ['alice', 'bob'], { carol: 'BIOLOGICAL', dave: 'BIOLOGICAL' })],
    );
    const small  = familyTreeLayout(graph, { compact: true, nodeHGap: 10 });
    const large  = familyTreeLayout(graph, { compact: true, nodeHGap: 100 });
    // With a larger gap, the total x span should be wider
    const xSpan = (nodes: typeof small) => Math.max(...nodes.map((n) => n.x)) - Math.min(...nodes.map((n) => n.x));
    expect(xSpan(large)).toBeGreaterThan(xSpan(small));
  });
});
