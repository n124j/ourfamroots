/**
 * Pedigree chart layout — horizontal binary ancestor tree.
 *
 * Focus person is on the LEFT; parents are one column to the right;
 * grandparents one more column, and so on.  The vertical space is split
 * by a binary-tree rule so each ancestor occupies an equal slice of height:
 *
 *               ┌── Grandfather (paternal)
 *          ┌── Father
 *          │    └── Grandmother (paternal)
 * [Focus] ─┤
 *          │    ┌── Grandfather (maternal)
 *          └── Mother
 *               └── Grandmother (maternal)
 *
 * Family-group (ring) nodes sit in the horizontal gap between the child
 * and that child's parents, centred vertically between the two parents.
 */

import type { ApiTreeGraph, PositionedNode } from '../../types';
import {
  PERSON_NODE_WIDTH  as PW,
  PERSON_NODE_HEIGHT as PH,
  FAMILY_NODE_SIZE   as FS,
} from '../../types';

const GEN_GAP  = 80;   // horizontal gap between generation columns
const MARGIN   = 40;
const SLOT_PAD = 40;   // vertical padding per slot at the deepest level

// ── Visible-IDs helper ───────────────────────────────────────────────────────

/**
 * Returns the set of node IDs (persons + family groups) that belong to the
 * ancestor subgraph of focusPersonId, up to maxGenerations deep.
 */
export function pedigreeChartVisibleIds(
  graph: ApiTreeGraph,
  focusPersonId: string,
  maxGenerations: number,
): Set<string> {
  const fgById = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));

  // personId → fgIds where that person is a CHILD
  const parentFGs = new Map<string, string[]>();
  for (const fg of graph.familyGroups) {
    for (const cId of Object.keys(fg.children)) {
      const list = parentFGs.get(cId) ?? [];
      list.push(fg.id);
      parentFGs.set(cId, list);
    }
  }

  const ids = new Set<string>([focusPersonId]);
  let frontier = [focusPersonId];

  for (let gen = 0; gen < maxGenerations && frontier.length > 0; gen++) {
    const next: string[] = [];
    for (const pid of frontier) {
      for (const fgId of parentFGs.get(pid) ?? []) {
        ids.add(fgId);
        const fg = fgById.get(fgId);
        if (!fg) continue;
        for (const parentId of fg.parentIds) {
          if (!ids.has(parentId)) {
            ids.add(parentId);
            next.push(parentId);
          }
        }
      }
    }
    frontier = next;
  }

  return ids;
}

// ── Layout ───────────────────────────────────────────────────────────────────

/**
 * Returns PositionedNode[] for a pedigree chart.
 *
 * @param maxGenerations  How many ancestor levels to show (default 4).
 */
export function pedigreeChartLayout(
  graph: ApiTreeGraph,
  focusPersonId: string,
  maxGenerations = 4,
): PositionedNode[] {
  const fgById = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));

  // person → fgId of the FG where this person is a CHILD (their parents' FG)
  const personParentFG = new Map<string, string>();
  for (const fg of graph.familyGroups) {
    for (const cId of Object.keys(fg.children)) {
      personParentFG.set(cId, fg.id);
    }
  }

  const visibleIds = pedigreeChartVisibleIds(graph, focusPersonId, maxGenerations);

  // ── Binary-tree position assignment ────────────────────────────────────────
  // Each ancestor gets (gen, slot):
  //   gen  = 0 for focus, 1 for parents, 2 for grandparents …
  //   slot = index within that generation (top → bottom, 0-indexed)
  //
  // For a person at (gen, slot), their parents are at
  //   (gen+1, slot*2)   ← first parent (father / upper)
  //   (gen+1, slot*2+1) ← second parent (mother / lower)

  interface BinPos { gen: number; slot: number }
  const personBin = new Map<string, BinPos>();
  const fgBin     = new Map<string, BinPos>(); // fgId → child's (gen, slot)

  personBin.set(focusPersonId, { gen: 0, slot: 0 });
  const queue: string[] = [focusPersonId];

  while (queue.length > 0) {
    const pid = queue.shift()!;
    const { gen, slot } = personBin.get(pid)!;
    if (gen >= maxGenerations) continue;

    const fgId = personParentFG.get(pid);
    if (!fgId || !visibleIds.has(fgId)) continue;

    const fg = fgById.get(fgId);
    if (!fg) continue;

    fgBin.set(fgId, { gen, slot });

    const visibleParents = fg.parentIds.filter((id) => visibleIds.has(id));
    visibleParents.forEach((parentId, i) => {
      if (!personBin.has(parentId)) {
        personBin.set(parentId, { gen: gen + 1, slot: slot * 2 + i });
        queue.push(parentId);
      }
    });
  }

  // ── Pixel coordinates ────────────────────────────────────────────────────
  // At maxGenerations depth there are 2^maxGenerations potential slots.
  // Each slot occupies (PH + SLOT_PAD) px; the slot centre is used for y.

  const numSlotsAtMax = Math.pow(2, maxGenerations);
  const slotH = PH + SLOT_PAD;

  const result: PositionedNode[] = [];

  // Persons
  for (const [personId, { gen, slot }] of personBin) {
    const slotsPerPerson = numSlotsAtMax / Math.pow(2, gen);
    const yCen = (slot + 0.5) * slotsPerPerson * slotH;
    result.push({
      id: personId,
      x: MARGIN + gen * (PW + GEN_GAP),
      y: yCen - PH / 2,
    });
  }

  // FG rings — in the horizontal gap, vertically between the two parents
  for (const [fgId, { gen, slot }] of fgBin) {
    const fg = fgById.get(fgId)!;
    const visibleParents = fg.parentIds.filter((id) => visibleIds.has(id));

    // x: centred inside the gap between this column and the next
    const x = MARGIN + gen * (PW + GEN_GAP) + PW + GEN_GAP / 2 - FS / 2;

    // y: midpoint between the two parents; falls back to child's y if only one parent
    let yCen: number;
    if (visibleParents.length >= 2) {
      const slotsPerParent = numSlotsAtMax / Math.pow(2, gen + 1);
      const y0 = (slot * 2 + 0.5) * slotsPerParent * slotH;
      const y1 = (slot * 2 + 1.5) * slotsPerParent * slotH;
      yCen = (y0 + y1) / 2;
    } else {
      const slotsPerChild = numSlotsAtMax / Math.pow(2, gen);
      yCen = (slot + 0.5) * slotsPerChild * slotH;
    }

    result.push({ id: fgId, x, y: yCen - FS / 2 });
  }

  return result;
}
