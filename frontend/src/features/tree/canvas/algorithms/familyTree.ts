/**
 * familyTreeLayout — compact generational family tree layout.
 *
 * Multi-spouse rule:
 *   A person with N marriages is the RIGHT anchor of their FIRST (chronologically
 *   earliest) marriage and the LEFT anchor of every subsequent marriage.  This
 *   places them between all their spouses:
 *
 *       [Sp1]──[ring1]──[Person]──[ring2]──[Sp2]
 *                  |                   |
 *             [children1]         [children2]
 *
 * Collision safety:
 *   A per-generation right-edge cursor (`rowRightX`) prevents any two nodes on
 *   the same row from overlapping, even when the subtree-width maths drifts for
 *   complex multi-marriage graphs.
 *
 * Other guarantees:
 *   - Every person at the same generation shares the same Y row.
 *   - Children sorted by birth year; siblings spread evenly below their FG ring.
 *   - FG ring centred between its two parents (symmetric union edges).
 *   - Subtree widths computed bottom-up to minimise wasted space.
 */

import type { ApiTreeGraph, PositionedNode } from '../../types';
import {
  PERSON_NODE_WIDTH  as PW,
  PERSON_NODE_HEIGHT as PH,
  FAMILY_NODE_SIZE   as FS,
} from '../../types';

const DEFAULT_COUPLE_GAP  = 20;   // px between adjacent spouse cards
const DEFAULT_SIBLING_GAP = 32;   // px between sibling subtrees
const DEFAULT_V_GAP       = 80;   // px between generation rows
const DEFAULT_MARGIN      = 40;

// ── Generation assignment ────────────────────────────────────────────────────

const YEARS_PER_GEN = 25;

function computeGenerations(
  graph: ApiTreeGraph,
  personParentFG: Map<string, string>,
  personChildFGs: Map<string, string[]>,
  fgById: Map<string, ApiTreeGraph['familyGroups'][number]>,
  alignByBirthYear = false,
): Map<string, number> {
  const gen = new Map<string, number>();

  if (alignByBirthYear) {
    // Seed each person's generation from their birth year so that disconnected
    // sub-trees whose real-world generations differ land on the correct rows.
    const knownYears = graph.persons
      .map((p) => p.birthYear)
      .filter((y): y is number => typeof y === 'number' && y > 1000);

    if (knownYears.length > 0) {
      const anchorYear = Math.min(...knownYears);
      for (const p of graph.persons) {
        if (typeof p.birthYear === 'number' && p.birthYear > 1000) {
          gen.set(p.id, Math.max(0, Math.round((p.birthYear - anchorYear) / YEARS_PER_GEN)));
        } else {
          gen.set(p.id, 0); // corrected by structural passes below
        }
      }
    } else {
      // No birth years available — fall through to structure-only seeding
      for (const p of graph.persons) gen.set(p.id, 0);
    }

    // Pull parents without a birth year toward their children's generation.
    // Without this, an unknown-birth-year parent stays at gen=0 even if all
    // their children are birth-year-seeded several rows lower.
    const noBirthYear = new Set(
      graph.persons
        .filter((p) => !(typeof p.birthYear === 'number' && p.birthYear > 1000))
        .map((p) => p.id),
    );
    let stable = false;
    while (!stable) {
      stable = true;
      for (const fg of graph.familyGroups) {
        const childGens = Object.keys(fg.children).map((c) => gen.get(c) ?? 0);
        if (childGens.length === 0) continue;
        const targetG = Math.min(...childGens) - 1;
        if (targetG <= 0) continue;
        for (const pid of fg.parentIds) {
          if (noBirthYear.has(pid) && (gen.get(pid) ?? 0) < targetG) {
            gen.set(pid, targetG);
            stable = false;
          }
        }
      }
    }
  } else {
    // Structure-only: BFS downward from root persons (those with no parent FG).
    for (const p of graph.persons) {
      if (!personParentFG.has(p.id)) gen.set(p.id, 0);
    }
    const queue: [string, number][] = [...gen].map(([id, g]) => [id, g]);
    while (queue.length > 0) {
      const [pid, g] = queue.shift()!;
      if ((gen.get(pid) ?? -1) > g) continue;
      gen.set(pid, g);
      for (const fgId of personChildFGs.get(pid) ?? []) {
        const fg = fgById.get(fgId)!;
        for (const childId of Object.keys(fg.children)) {
          if ((gen.get(childId) ?? -1) < g + 1) queue.push([childId, g + 1]);
        }
      }
    }
    for (const p of graph.persons) {
      if (!gen.has(p.id)) gen.set(p.id, 0);
    }
  }

  // Structural promotion: co-parents share the same generation row; children
  // must always be strictly one generation below their parents.
  let stable = false;
  while (!stable) {
    stable = true;
    for (const fg of graph.familyGroups) {
      const pGens = fg.parentIds.map((id) => gen.get(id) ?? 0);
      const maxG  = pGens.length ? Math.max(...pGens) : 0;
      for (const pid of fg.parentIds) {
        if ((gen.get(pid) ?? 0) < maxG) { gen.set(pid, maxG); stable = false; }
      }
      const childG = maxG + 1;
      for (const cId of Object.keys(fg.children)) {
        if ((gen.get(cId) ?? 0) < childG) { gen.set(cId, childG); stable = false; }
      }
    }
  }

  return gen;
}

// ── Main export ──────────────────────────────────────────────────────────────

export function familyTreeLayout(
  graph: ApiTreeGraph,
  opts: { nodeHGap?: number; nodeVGap?: number; coupleGap?: number; margin?: number; alignByBirthYear?: boolean } = {},
): PositionedNode[] {
  if (graph.persons.length === 0) return [];

  const sibGap    = opts.nodeHGap  ?? DEFAULT_SIBLING_GAP;
  const vGap      = opts.nodeVGap  ?? DEFAULT_V_GAP;
  const COUPLE_GAP = opts.coupleGap ?? DEFAULT_COUPLE_GAP;
  const MARGIN     = opts.margin    ?? DEFAULT_MARGIN;

  // ── Lookup maps ──────────────────────────────────────────────────────────────
  const fgById     = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));
  const personById = new Map(graph.persons.map((p)  => [p.id, p]));

  // childId → fgId (the one FG this person is a child in)
  const personParentFG = new Map<string, string>();
  // parentId → [fgId, ...] (all FGs where this person is a parent)
  const personChildFGs = new Map<string, string[]>();

  for (const fg of graph.familyGroups) {
    for (const cId of Object.keys(fg.children)) personParentFG.set(cId, fg.id);
    for (const pId of fg.parentIds) {
      const list = personChildFGs.get(pId) ?? [];
      list.push(fg.id);
      personChildFGs.set(pId, list);
    }
  }

  // Sort each person's FG list by the earliest birth year among their children
  // so FG1 = chronologically first marriage.
  for (const fgIds of personChildFGs.values()) {
    fgIds.sort((a, b) => {
      const minY = (fgId: string) =>
        Object.keys(fgById.get(fgId)!.children).reduce(
          (m, id) => Math.min(m, personById.get(id)?.birthYear ?? 9999), 9999
        );
      return minY(a) - minY(b);
    });
  }

  // ── Phase 1: generation numbers ──────────────────────────────────────────────
  const genMap = computeGenerations(graph, personParentFG, personChildFGs, fgById, opts.alignByBirthYear ?? false);

  const ROW_H = PH + vGap;
  const yPerson = (id: string)  => MARGIN + (genMap.get(id) ?? 0) * ROW_H;
  const yFG     = (fgId: string) => {
    const fg = fgById.get(fgId)!;
    const maxParentGen = fg.parentIds.length
      ? Math.max(...fg.parentIds.map((id) => genMap.get(id) ?? 0))
      : 0;
    return MARGIN + maxParentGen * ROW_H + PH + vGap / 2 - FS / 2;
  };

  // ── Phase 2: bottom-up subtree widths ────────────────────────────────────────
  const wMemo       = new Map<string, number>();
  const wInProgress = new Set<string>(); // cycle guard for mutual personW ↔ fgHalfW recursion

  function personW(id: string): number {
    const k = `p:${id}`;
    if (wMemo.has(k)) return wMemo.get(k)!;
    // Break the cycle: personW(A) → fgHalfW(FG, A) → personW(spouse)
    //                             → fgHalfW(FG, spouse) → personW(A) ← cycle
    if (wInProgress.has(k)) return PW;
    wInProgress.add(k);

    const fgIds = personChildFGs.get(id) ?? [];
    let w: number;

    if (fgIds.length === 0) {
      w = PW;
    } else if (fgIds.length === 1) {
      w = fgW(fgIds[0]);
    } else {
      // Multi-marriage: person sits between Sp1 (left) and Sp2..SpN (right).
      // Width = leftHalf(FG1) + PW + rightHalves(FG2..FGn)
      const leftW  = fgHalfW(fgIds[0], id, 'left');
      const rightW = fgIds.slice(1).reduce(
        (s, fgId, i) => s + (i > 0 ? sibGap : 0) + fgHalfW(fgId, id, 'right'),
        0,
      );
      w = leftW + PW + rightW;
    }

    wInProgress.delete(k);
    wMemo.set(k, w);
    return w;
  }

  function fgW(fgId: string): number {
    const k = `fg:${fgId}`;
    if (wMemo.has(k)) return wMemo.get(k)!;
    const fg       = fgById.get(fgId)!;
    const coupleW  = fg.parentIds.length >= 2 ? PW + COUPLE_GAP + PW : PW;
    const children = sortedChildren(fg);
    if (!children.length) { wMemo.set(k, coupleW); return coupleW; }
    const childrenW = children.reduce((s, cId, i) => s + personW(cId) + (i > 0 ? sibGap : 0), 0);
    const w = Math.max(coupleW, childrenW);
    wMemo.set(k, w);
    return w;
  }

  /**
   * Half-width of fgId on the given side of anchorId.
   * 'left'  → the space occupied by the non-anchor spouse + their children + COUPLE_GAP
   * 'right' → COUPLE_GAP + the space occupied by the non-anchor spouse + their children
   */
  function fgHalfW(fgId: string, anchorId: string, side: 'left' | 'right'): number {
    const fg       = fgById.get(fgId)!;
    const spouseId = fg.parentIds.find((id) => id !== anchorId);
    const spouseW  = spouseId ? personW(spouseId) : 0;
    const children = sortedChildren(fg);
    const childrenW = children.reduce((s, cId, i) => s + personW(cId) + (i > 0 ? sibGap : 0), 0);
    const contentW  = Math.max(childrenW, spouseW);
    return side === 'left'
      ? contentW + (spouseId ? COUPLE_GAP : 0)
      : (spouseId ? COUPLE_GAP : 0) + contentW;
  }

  // ── Phase 3: placement ───────────────────────────────────────────────────────

  const result:   PositionedNode[] = [];
  const posMap    = new Map<string, number>(); // personId → placed x (left edge)
  const placedFGs = new Set<string>();

  // Per-generation right-edge cursor: guarantees no two nodes on the same row
  // overlap even when subtree widths drift in complex multi-marriage graphs.
  const rowRightX = new Map<number, number>(); // gen → rightmost (x + PW)

  function pushPerson(id: string, preferredX: number) {
    const gen  = genMap.get(id) ?? 0;
    // Clamp rightward so we never land on an already-occupied slot
    const minX = (rowRightX.get(gen) ?? MARGIN - COUPLE_GAP) + COUPLE_GAP;
    const x    = Math.max(preferredX, minX);
    result.push({ id, x, y: yPerson(id) });
    posMap.set(id, x);
    rowRightX.set(gen, Math.max(rowRightX.get(gen) ?? -Infinity, x + PW));
  }

  // Children of a family group, sorted oldest → youngest
  function sortedChildren(fg: ApiTreeGraph['familyGroups'][number]): string[] {
    return Object.keys(fg.children).sort(
      (a, b) => (personById.get(a)?.birthYear ?? 9999) - (personById.get(b)?.birthYear ?? 9999),
    );
  }

  /**
   * Ordered parent pair [left, right] for a family group.
   *
   * Multi-marriage rule:
   *   If a parent has N > 1 marriages and this is their FIRST one, they are
   *   the RIGHT parent so their spouse lands to their left.  For all later
   *   marriages they are the LEFT parent so new spouses land to their right.
   *
   * Single-marriage default: male left, female right; ties by birth year.
   */
  function orderedParents(fg: ApiTreeGraph['familyGroups'][number]): [string | undefined, string | undefined] {
    if (fg.parentIds.length === 0) return [undefined, undefined];
    if (fg.parentIds.length === 1) return [fg.parentIds[0], undefined];

    const [a, b] = fg.parentIds;
    const aFGs   = personChildFGs.get(a) ?? [];
    const bFGs   = personChildFGs.get(b) ?? [];

    // a has multiple marriages and this is a's first → a goes RIGHT
    if (aFGs.length > 1 && aFGs[0] === fg.id) return [b, a];
    // a has multiple marriages and this is NOT a's first → a goes LEFT
    if (aFGs.length > 1 && aFGs[0] !== fg.id) return [a, b];

    // b has multiple marriages and this is b's first → b goes RIGHT
    if (bFGs.length > 1 && bFGs[0] === fg.id) return [a, b];
    // b has multiple marriages and this is NOT b's first → b goes LEFT
    if (bFGs.length > 1 && bFGs[0] !== fg.id) return [b, a];

    // Single marriage for both: male left, female right; ties by birth year
    const pa = personById.get(a);
    const pb = personById.get(b);
    if (pa?.sex === 'MALE'    && pb?.sex !== 'MALE') return [a, b];
    if (pa?.sex !== 'MALE'    && pb?.sex === 'MALE') return [b, a];
    return (pa?.birthYear ?? 9999) <= (pb?.birthYear ?? 9999) ? [a, b] : [b, a];
  }

  function placeFG(fgId: string, suggestedLeftX: number) {
    if (placedFGs.has(fgId)) return;
    placedFGs.add(fgId);

    const fg          = fgById.get(fgId)!;
    const myW         = fgW(fgId);
    const suggestedCx = suggestedLeftX + myW / 2;

    const [p1Id, p2Id] = orderedParents(fg);

    // ── Place parents ────────────────────────────────────────────────────────
    if (p1Id && p2Id) {
      const p1Fixed = posMap.has(p1Id);
      const p2Fixed = posMap.has(p2Id);

      if (!p1Fixed && !p2Fixed) {
        // Both fresh: centre couple on suggestedCx
        pushPerson(p1Id, suggestedCx - COUPLE_GAP / 2 - PW);
        pushPerson(p2Id, suggestedCx + COUPLE_GAP / 2);
      } else if (p1Fixed && !p2Fixed) {
        // p1 already placed: put p2 immediately to its right
        // rowRightX clamping inside pushPerson prevents collision with any
        // previously placed node on the same row (e.g., an earlier spouse).
        const adjacentX = posMap.get(p1Id)! + PW + COUPLE_GAP;
        pushPerson(p2Id, adjacentX);
      } else if (!p1Fixed && p2Fixed) {
        // p2 already placed: put p1 to the left, but at least MARGIN
        const adjacentX = posMap.get(p2Id)! - COUPLE_GAP - PW;
        // Don't use rowRightX here — we're going left intentionally.
        // Guard: never go below MARGIN.
        const x = Math.max(adjacentX, MARGIN);
        result.push({ id: p1Id, x, y: yPerson(p1Id) });
        posMap.set(p1Id, x);
        rowRightX.set(
          genMap.get(p1Id) ?? 0,
          Math.max(rowRightX.get(genMap.get(p1Id) ?? 0) ?? -Infinity, x + PW),
        );
      }
    } else if (p1Id) {
      if (!posMap.has(p1Id)) pushPerson(p1Id, suggestedCx - PW / 2);
    }

    // ── Children sorted by birth year ────────────────────────────────────────
    const children = sortedChildren(fg);

    if (!children.length) {
      // No children: ring sits between the parents
      const px1 = p1Id ? posMap.get(p1Id) : undefined;
      const px2 = p2Id ? posMap.get(p2Id) : undefined;
      let ringCx = suggestedCx;
      if (px1 !== undefined && px2 !== undefined) ringCx = (px1 + px2 + PW) / 2;
      else if (px1 !== undefined)                 ringCx = px1 + PW / 2;
      else if (px2 !== undefined)                 ringCx = px2 + PW / 2;
      result.push({ id: fgId, x: ringCx - FS / 2, y: yFG(fgId) });
      return;
    }

    const totalChildW = children.reduce((s, cId, i) => s + personW(cId) + (i > 0 ? sibGap : 0), 0);
    let childX = suggestedCx - totalChildW / 2;

    for (const cId of children) {
      const cw   = personW(cId);
      const cFGs = personChildFGs.get(cId) ?? [];

      if (!posMap.has(cId)) {
        if (cFGs.length > 0) {
          let fgX = childX;
          for (const cFgId of cFGs) {
            if (!placedFGs.has(cFgId)) {
              placeFG(cFgId, fgX);
              fgX += fgW(cFgId) + sibGap;
            }
          }
          if (!posMap.has(cId)) pushPerson(cId, childX + (cw - PW) / 2);
        } else {
          pushPerson(cId, childX + (cw - PW) / 2);
        }
      }
      childX += cw + sibGap;
    }

    // ── Ring centred between the two parents ─────────────────────────────────
    // Falls back to children midpoint when no parents are placed.
    const px1 = p1Id ? posMap.get(p1Id) : undefined;
    const px2 = p2Id ? posMap.get(p2Id) : undefined;
    let ringCx: number;
    if (px1 !== undefined && px2 !== undefined) {
      ringCx = (px1 + px2 + PW) / 2;
    } else if (px1 !== undefined) {
      ringCx = px1 + PW / 2;
    } else if (px2 !== undefined) {
      ringCx = px2 + PW / 2;
    } else {
      const xs = children.map((c) => posMap.get(c)).filter((x): x is number => x !== undefined);
      ringCx = xs.length ? (Math.min(...xs) + Math.max(...xs) + PW) / 2 : suggestedCx;
    }
    result.push({ id: fgId, x: ringCx - FS / 2, y: yFG(fgId) });
  }

  // ── Kick-off: root FGs, sorted by earliest parent birth year ─────────────────
  const rootFGs = graph.familyGroups
    .filter((fg) => fg.parentIds.every((pid) => !personParentFG.has(pid)))
    .sort((a, b) => {
      const minY = (fg: typeof a) =>
        fg.parentIds.reduce((m, id) => Math.min(m, personById.get(id)?.birthYear ?? 9999), 9999);
      return minY(a) - minY(b);
    });

  // Helper: rightmost placed x at a given generation (falls back to curX).
  // Using this instead of fgW() prevents inflated estimates from pushing
  // disconnected sub-trees far to the right.
  const actualRightX = (gen: number, fallback: number) =>
    Math.max(rowRightX.get(gen) ?? fallback, fallback);

  let curX = MARGIN;
  for (const fg of rootFGs) {
    placeFG(fg.id, curX);
    // Advance by ACTUAL rightmost position, not estimated fgW.
    const parentGen = fg.parentIds.length
      ? Math.max(...fg.parentIds.map((id) => genMap.get(id) ?? 0))
      : 0;
    curX = actualRightX(parentGen, curX + PW) + sibGap;
  }

  // ── Root persons not reached by any root FG (isolated / single parents) ──────
  // Reset curX to actual rightmost gen-0 position before placing these.
  curX = actualRightX(0, MARGIN - sibGap) + sibGap;

  const rootPersons = graph.persons
    .filter((p) => !personParentFG.has(p.id))
    .sort((a, b) => (a.birthYear ?? 9999) - (b.birthYear ?? 9999));

  for (const p of rootPersons) {
    if (posMap.has(p.id)) continue;
    const pGen = genMap.get(p.id) ?? 0;
    const cFGs = personChildFGs.get(p.id) ?? [];
    if (cFGs.length > 0) {
      for (const cFgId of cFGs) {
        if (!placedFGs.has(cFgId)) {
          placeFG(cFgId, curX);
          curX = actualRightX(pGen, curX + PW) + sibGap;
        }
      }
      if (!posMap.has(p.id)) pushPerson(p.id, curX + (personW(p.id) - PW) / 2);
    } else {
      pushPerson(p.id, curX);
    }
    curX = actualRightX(pGen, curX + PW) + sibGap;
  }

  // ── Orphaned FG nodes (parents placed but FG missed) ─────────────────────────
  for (const fg of graph.familyGroups) {
    if (placedFGs.has(fg.id)) continue;
    const parentXs = fg.parentIds
      .map((pid) => posMap.get(pid))
      .filter((x): x is number => x !== undefined);
    let ringX: number;
    if (parentXs.length >= 2) {
      ringX = (parentXs[0] + parentXs[1] + PW) / 2 - FS / 2;
    } else if (parentXs.length === 1) {
      ringX = parentXs[0] + PW / 2 - FS / 2;
    } else {
      ringX = curX;
      curX += FS + sibGap;
    }
    result.push({ id: fg.id, x: ringX, y: yFG(fg.id) });
  }

  return result;
}
