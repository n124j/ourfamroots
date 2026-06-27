/**
 * Tree visualization types.
 * Extends React Flow's generic Node/Edge with genealogy-specific data.
 */

import type { Node, Edge } from 'reactflow';

// ── Enums ──────────────────────────────────────────────────────────────────

export type Sex = 'MALE' | 'FEMALE' | 'OTHER' | 'UNKNOWN';

export type ParentageType =
  | 'BIOLOGICAL'
  | 'ADOPTIVE'
  | 'STEP'
  | 'FOSTER'
  | 'UNKNOWN';

export type UnionType =
  | 'MARRIAGE'
  | 'PARTNERSHIP'
  | 'COHABITATION'
  | 'UNKNOWN';

export type LayoutMode =
  | 'compact'            // dagre TB — compact top-to-bottom, groups related members together
  | 'generation'         // dagre TB — simple top-to-bottom generation hierarchy
  | 'vertical'           // familyTree algorithm — multi-marriage aware generational layout
  | 'horizontal'         // dagre LR — left-to-right
  | 'ancestor'           // ancestors of focus person going up
  | 'descendant'         // descendants of focus person going down
  | 'descendant-family'  // descendants with spouses — couples shown together going down
  | 'ancestor-family'    // ancestors with spouses — couples shown together going up
  | 'fan'                // polar fan chart — semicircle (180°)
  | 'ancestry-fan'       // ancestry fan chart — full circle (360°)
  | 'pedigree';          // horizontal binary ancestor tree (focus left, ancestors right)

// ── Node data types ────────────────────────────────────────────────────────

export interface PersonNodeData {
  /** Node type discriminator */
  kind: 'person';

  personId: string;
  treeId: string;

  displayGivenName: string;
  displaySurname: string;
  sex: Sex;

  birthYear?: number;
  deathYear?: number;
  isLiving: boolean;
  isDeceased: boolean;

  /** URL to profile photo thumbnail (80×80) */
  photoUrl?: string;

  /** Whether this person is the focus/root of the current layout */
  isFocus: boolean;

  /** Whether the subtree below this person is currently expanded */
  isExpanded: boolean;

  /** Whether this node has hidden children (collapsed) */
  hasHiddenChildren: boolean;

  /** Whether this node has hidden parents (collapsed upward) */
  hasHiddenParents: boolean;

  /** Generation index relative to focus (0 = focus, -1 = parent, +1 = child) */
  generation: number;

  birthDate?: string;
  deathDate?: string;
  bornCity?: string;
  bornCountry?: string;
  diedCity?: string;
  diedCountry?: string;
  notes?: string;
}

export interface FamilyGroupNodeData {
  /** Node type discriminator */
  kind: 'family-group';

  familyGroupId: string;
  treeId: string;
  unionType: UnionType;

  /** IDs of the parent persons in this group */
  parentIds: string[];

  /** Whether to show the union type icon */
  showUnionIcon: boolean;
}

// ── Edge data types ────────────────────────────────────────────────────────

/** Edge from a Person to a FamilyGroup (as a parent member) */
export interface UnionEdgeData {
  kind: 'union';
  unionType: UnionType;
  isHighlighted?: boolean;
  /** 1-based ordinal when this person has multiple unions of the same type (e.g. 2 → "2nd Marriage") */
  unionOrdinal?: number;
  /** User-defined label overriding the auto-generated ordinal label */
  customLabel?: string;
  /** Whether this union has been marked as divorced */
  isDivorced?: boolean;
  unionDate?: string;
  unionDateYear?: number;
  unionEndDate?: string;
  unionEndDateYear?: number;
}

/** Edge from a FamilyGroup to a Person (as a child member) */
export interface ParentChildEdgeData {
  kind: 'parent-child';
  parentageType: ParentageType;
  isHighlighted?: boolean;
}

// ── React Flow node / edge aliases ─────────────────────────────────────────

export type PersonRFNode = Node<PersonNodeData, 'person'>;
export type FamilyGroupRFNode = Node<FamilyGroupNodeData, 'family-group'>;
export type TreeNode = PersonRFNode | FamilyGroupRFNode;

export type UnionRFEdge = Edge<UnionEdgeData>;
export type ParentChildRFEdge = Edge<ParentChildEdgeData>;
export type TreeEdge = UnionRFEdge | ParentChildRFEdge;

// ── API response shape (mirrors backend schemas) ───────────────────────────

export interface ApiPerson {
  id: string;
  treeId: string;
  displayGivenName: string;
  displaySurname: string;
  sex: Sex;
  /** Full ISO date string "YYYY-MM-DD" */
  birthDate?: string;
  deathDate?: string;
  /** Year only — used when full date is unknown */
  birthYear?: number;
  deathYear?: number;
  isLiving: boolean;
  isDeceased: boolean;
  photoUrl?: string;
  bornCity?: string;
  bornCountry?: string;
  diedCity?: string;
  diedCountry?: string;
  notes?: string;
}

export interface ApiMembership {
  personId: string;
  role: 'PARENT' | 'CHILD';
  parentageType: ParentageType;
}

export interface ApiFamilyGroup {
  id: string;
  treeId: string;
  unionType: UnionType;
  /** User-defined label overriding the auto-generated ordinal (e.g. "Church Wedding") */
  customLabel?: string;
  /** Whether this union has been marked as divorced */
  isDivorced?: boolean;
  /** Date the union started (ISO "YYYY-MM-DD") */
  unionDate?: string;
  /** Year only — when full date is unknown */
  unionDateYear?: number;
  /** Date the union ended (ISO "YYYY-MM-DD") */
  unionEndDate?: string;
  /** Year only — when full date is unknown */
  unionEndDateYear?: number;
  parentIds: string[];
  children: Record<string, ParentageType>; // personId → parentageType
}

export interface ApiTreeGraph {
  treeId: string;
  persons: ApiPerson[];
  familyGroups: ApiFamilyGroup[];
}

// ── Layout algorithm input/output ──────────────────────────────────────────

export interface LayoutOptions {
  mode: LayoutMode;
  direction: 'TB' | 'LR';
  /** ID of the person who is the focal point (for ancestor/descendant/fan) */
  focusPersonId?: string;
  /** Horizontal gap between nodes (px) */
  nodeHGap: number;
  /** Vertical gap between ranks (px) */
  nodeVGap: number;
  /** Pixel dimensions of a person node */
  personNodeWidth: number;
  personNodeHeight: number;
  /** Pixel dimensions of a family group node */
  familyNodeWidth: number;
  familyNodeHeight: number;
}

export interface PositionedNode {
  id: string;
  x: number;
  y: number;
}

// ── Canvas store shape (used by canvas.store.ts) ───────────────────────────

export interface CanvasState {
  treeId: string | null;
  layoutMode: LayoutMode;
  focusPersonId: string | null;
  selectedPersonId: string | null;
  expandedNodeIds: Set<string>;
  zoom: number;
  pan: { x: number; y: number };
}

// ── Colour helpers ─────────────────────────────────────────────────────────

export const SEX_BORDER_COLOR: Record<Sex, string> = {
  MALE: '#3b82f6',
  FEMALE: '#ec4899',
  OTHER: '#8b5cf6',
  UNKNOWN: '#94a3b8',
};

export const SEX_BG_COLOR: Record<Sex, string> = {
  MALE: '#eff6ff',
  FEMALE: '#fdf2f8',
  OTHER: '#f5f3ff',
  UNKNOWN: '#f8fafc',
};

export const PARENTAGE_STROKE: Record<ParentageType, string> = {
  BIOLOGICAL: 'solid',
  ADOPTIVE: '8 4',     // SVG dasharray
  STEP: '4 4',
  FOSTER: '8 4 2 4',
  UNKNOWN: '4 4',
};

export const UNION_STROKE: Record<UnionType, string> = {
  MARRIAGE: 'solid',
  PARTNERSHIP: '6 3',
  COHABITATION: '6 6',
  UNKNOWN: '4 4',
};

// ── Node size constants ────────────────────────────────────────────────────

export const PERSON_NODE_WIDTH = 200;
export const PERSON_NODE_HEIGHT = 88;
export const FAMILY_NODE_SIZE = 24;

export const DEFAULT_LAYOUT_OPTIONS: LayoutOptions = {
  mode: 'ancestor',
  direction: 'TB',
  nodeHGap: 32,
  nodeVGap: 80,
  personNodeWidth: PERSON_NODE_WIDTH,
  personNodeHeight: PERSON_NODE_HEIGHT,
  familyNodeWidth: FAMILY_NODE_SIZE,
  familyNodeHeight: FAMILY_NODE_SIZE,
};
