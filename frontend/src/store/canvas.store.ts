/**
 * canvas.store — Zustand store for tree canvas state.
 *
 * Owns: viewport, selected node, layout mode, focus person, expand/collapse set.
 * Does NOT own server data (that's React Query's job).
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type { LayoutMode, UnionType, ParentageType } from '@features/tree/types';

export interface SelectedEdge {
  id: string;
  /** 'union' = person→family-group edge; 'parent-child' = family-group→person edge */
  kind: 'union' | 'parent-child';
  /** union: the parent personId | parent-child: the familyGroupId */
  source: string;
  /** union: the familyGroupId | parent-child: the child personId */
  target: string;
  unionType?: UnionType;
  parentageType?: ParentageType;
}

interface CanvasStore {
  treeId: string | null;
  setTreeId: (id: string | null) => void;

  focusPersonId: string | null;
  setFocusPersonId: (id: string | null) => void;

  selectedPersonId: string | null;
  setSelectedPersonId: (id: string | null) => void;

  selectedEdge: SelectedEdge | null;
  setSelectedEdge: (edge: SelectedEdge | null) => void;

  layoutMode: LayoutMode;
  setLayoutMode: (mode: LayoutMode) => void;

  zoom: number;
  setZoom: (z: number) => void;
  pan: { x: number; y: number };
  setPan: (pan: { x: number; y: number }) => void;

  expandedNodeIds: Set<string>;
  setExpandedNodeIds: (ids: Set<string>) => void;

  toggleExpand: ((personId: string, direction: 'children' | 'parents') => void) | null;
  setToggleExpand: (fn: (personId: string, direction: 'children' | 'parents') => void) => void;

  setSetSelectedPersonId: (fn: (id: string | null) => void) => void;

  layoutResetKey: number;
  bumpLayoutReset: () => void;

  isPdfMode: boolean;
  setIsPdfMode: (v: boolean) => void;

  reset: () => void;
}

const initialState = {
  treeId: null,
  focusPersonId: null,
  selectedPersonId: null,
  selectedEdge: null,
  layoutMode: 'vertical' as LayoutMode, // "Vertical (multi-marriage aware)" — default on tree open
  zoom: 0.8,
  pan: { x: 0, y: 0 },
  expandedNodeIds: new Set<string>(),
  toggleExpand: null,
  layoutResetKey: 0,
  isPdfMode: false,
};

export const useCanvasStore = create<CanvasStore>()(
  devtools(
    (set) => ({
      ...initialState,

      setTreeId: (id) => set({ treeId: id }),
      setFocusPersonId: (id) => set({ focusPersonId: id }),
      setSelectedPersonId: (id) => set({ selectedPersonId: id }),
      setSelectedEdge: (edge) => set({ selectedEdge: edge }),
      setLayoutMode: (mode) => set({ layoutMode: mode }),
      setZoom: (zoom) => set({ zoom }),
      setPan: (pan) => set({ pan }),
      setExpandedNodeIds: (ids) => set({ expandedNodeIds: ids }),
      setToggleExpand: (fn) => set({ toggleExpand: fn }),
      bumpLayoutReset: () => set((s) => ({ layoutResetKey: s.layoutResetKey + 1 })),
      setIsPdfMode: (v) => set({ isPdfMode: v }),
      setSetSelectedPersonId: (_fn) => {
        // The store itself manages selectedPersonId; this is a no-op stub.
        // PersonNode calls useCanvasStore((s) => s.setSelectedPersonId) directly.
      },
      reset: () => set(initialState),
    }),
    { name: 'canvas-store' }
  )
);
