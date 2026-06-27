/**
 * useTreeTransform — converts API graph data to React Flow nodes + edges.
 *
 * This is a pure data transformation (no layout positions yet).
 * Positions are set to {0, 0} here; the layout hook patches them.
 */

import type { ApiTreeGraph, TreeNode, TreeEdge, PersonNodeData, FamilyGroupNodeData } from '../types';
import { PERSON_NODE_WIDTH, PERSON_NODE_HEIGHT, FAMILY_NODE_SIZE } from '../types';

export interface TransformOptions {
  focusPersonId?: string;
  expandedNodeIds: Set<string>;
}

export interface TransformResult {
  nodes: TreeNode[];
  edges: TreeEdge[];
}

/**
 * Pure function — call it inside useMemo when graph or options change.
 */
export function transformGraphToFlow(
  graph: ApiTreeGraph,
  options: TransformOptions
): TransformResult {
  const { focusPersonId, expandedNodeIds } = options;

  // Build set of persons that have hidden children (for expand button)
  const personHasChildren = new Set<string>();
  const personHasParents = new Set<string>();

  const fgById = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));

  for (const fg of graph.familyGroups) {
    // Parents of children
    for (const childId of Object.keys(fg.children)) {
      personHasParents.add(childId);
    }
    // Children of parents
    for (const parentId of fg.parentIds) {
      if (Object.keys(fg.children).length > 0) {
        personHasChildren.add(parentId);
      }
    }
  }

  // ── Person nodes ─────────────────────────────────────────────────────────

  const personNodes: TreeNode[] = graph.persons.map((person) => {
    const isExpanded = expandedNodeIds.has(person.id);
    const data: PersonNodeData = {
      kind: 'person',
      personId: person.id,
      treeId: person.treeId,
      displayGivenName: person.displayGivenName,
      displaySurname: person.displaySurname,
      sex: person.sex,
      birthDate: person.birthDate,
      deathDate: person.deathDate,
      birthYear: person.birthYear,
      deathYear: person.deathYear,
      isLiving: person.isLiving,
      isDeceased: person.isDeceased,
      photoUrl: person.photoUrl,
      isFocus: person.id === focusPersonId,
      isExpanded,
      hasHiddenChildren: personHasChildren.has(person.id) && !isExpanded,
      hasHiddenParents: personHasParents.has(person.id) && !isExpanded,
      generation: 0, // patched by layout
      bornCity: person.bornCity,
      bornCountry: person.bornCountry,
      diedCity: person.diedCity,
      diedCountry: person.diedCountry,
      notes: person.notes,
    };

    return {
      id: person.id,
      type: 'person' as const,
      position: { x: 0, y: 0 }, // layout algorithm sets this
      data,
      width: PERSON_NODE_WIDTH,
      height: PERSON_NODE_HEIGHT,
      draggable: true,
      selectable: true,
    };
  });

  // ── Family group nodes ────────────────────────────────────────────────────

  const familyGroupNodes: TreeNode[] = graph.familyGroups.map((fg) => {
    const data: FamilyGroupNodeData = {
      kind: 'family-group',
      familyGroupId: fg.id,
      treeId: fg.treeId,
      unionType: fg.unionType,
      parentIds: fg.parentIds,
      showUnionIcon: fg.unionType !== 'UNKNOWN' && fg.parentIds.length >= 2,
    };

    return {
      id: fg.id,
      type: 'family-group' as const,
      position: { x: 0, y: 0 },
      data,
      width: FAMILY_NODE_SIZE,
      height: FAMILY_NODE_SIZE,
      draggable: false,
      selectable: true,
    };
  });

  // ── Edges ─────────────────────────────────────────────────────────────────

  // Pre-compute per-person union ordinals (1-based) for each union type.
  // Only populated when a person has 2+ unions of the same type.
  // FGs are sorted chronologically (by union date, then earliest child birth year).
  const unionOrdinalKey = (personId: string, fgId: string) => `${personId}::${fgId}`;
  const unionOrdinals = new Map<string, number>();

  const fgLookup = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));

  const fgDateOrder = (fg: typeof graph.familyGroups[number] | undefined): number => {
    if (!fg) return 9999;
    if (fg.unionDateYear != null) return fg.unionDateYear;
    if (fg.unionDate) {
      const y = parseInt(fg.unionDate.slice(0, 4), 10);
      if (!isNaN(y)) return y;
    }
    const childYears = Object.keys(fg.children)
      .map((cid) => graph.persons.find((p) => p.id === cid)?.birthYear)
      .filter((y): y is number => typeof y === 'number');
    return childYears.length > 0 ? Math.min(...childYears) : 9999;
  };

  const personFgs = new Map<string, Array<{ fgId: string; unionType: string }>>();
  for (const fg of graph.familyGroups) {
    for (const parentId of fg.parentIds) {
      if (!personFgs.has(parentId)) personFgs.set(parentId, []);
      personFgs.get(parentId)!.push({ fgId: fg.id, unionType: fg.unionType });
    }
  }
  for (const fgs of personFgs.values()) {
    fgs.sort((a, b) => fgDateOrder(fgLookup.get(a.fgId)) - fgDateOrder(fgLookup.get(b.fgId)));
  }
  for (const [personId, fgs] of personFgs) {
    const byType = new Map<string, string[]>();
    for (const { fgId, unionType } of fgs) {
      if (!byType.has(unionType)) byType.set(unionType, []);
      byType.get(unionType)!.push(fgId);
    }
    for (const fgIds of byType.values()) {
      if (fgIds.length >= 2) {
        fgIds.forEach((fgId, idx) => {
          unionOrdinals.set(unionOrdinalKey(personId, fgId), idx + 1);
        });
      }
    }
  }

  const edges: TreeEdge[] = [];

  for (const fg of graph.familyGroups) {
    // Parent → FamilyGroup (union edge)
    //
    // For each family group we show at most ONE label (ordinal or customLabel).
    // We assign it to the parent with the most unions of this type — that parent's
    // ordinal gives the most useful context ("3rd Marriage" from the person who
    // has had 3 marriages, not "1st Marriage" from the partner's perspective).
    // If no parent has an ordinal (everyone has exactly 1 marriage of this type),
    // the customLabel (if any) falls back to the first parent's edge.
    const parentOrdinals = fg.parentIds.map((pid) =>
      unionOrdinals.get(unionOrdinalKey(pid, fg.id))
    );

    let labelIdx = -1;
    let bestCount = 0;
    let bestOrdinal = 0;
    fg.parentIds.forEach((pid, i) => {
      const pFgs = personFgs.get(pid);
      const typeCount = pFgs?.filter((f) => f.unionType === fg.unionType).length ?? 0;
      const ord = parentOrdinals[i] ?? 0;
      if (typeCount > bestCount || (typeCount === bestCount && ord > bestOrdinal)) {
        bestCount = typeCount;
        bestOrdinal = ord;
        labelIdx = i;
      }
    });
    const customLabelIdx = labelIdx >= 0 ? labelIdx : 0;

    for (let i = 0; i < fg.parentIds.length; i++) {
      const parentId = fg.parentIds[i];
      edges.push({
        id: `union-${parentId}-${fg.id}`,
        source: parentId,
        target: fg.id,
        type: 'union' as const,
        data: {
          kind: 'union',
          unionType: fg.unionType,
          unionOrdinal: i === labelIdx ? parentOrdinals[i] : undefined,
          customLabel: i === customLabelIdx ? fg.customLabel : undefined,
          isDivorced: fg.isDivorced,
          unionDate: fg.unionDate,
          unionDateYear: fg.unionDateYear,
          unionEndDate: fg.unionEndDate,
          unionEndDateYear: fg.unionEndDateYear,
        },
        animated: false,
      } as TreeEdge);
    }

    // FamilyGroup → Child (parent-child edge)
    for (const [childId, parentageType] of Object.entries(fg.children)) {
      edges.push({
        id: `child-${fg.id}-${childId}`,
        source: fg.id,
        target: childId,
        type: 'parent-child' as const,
        data: { kind: 'parent-child', parentageType },
        animated: false,
      } as TreeEdge);
    }
  }

  return {
    nodes: [...personNodes, ...familyGroupNodes],
    edges,
  };
}
