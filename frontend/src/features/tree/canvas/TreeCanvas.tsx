/**
 * TreeCanvas — the main interactive genealogy graph component.
 *
 * Responsibilities:
 *   - Renders the React Flow canvas with custom node/edge types
 *   - Orchestrates layout algorithm selection
 *   - Manages expand/collapse
 *   - Handles node selection → opens side panel
 *   - Person nodes are freely draggable (positions persist until layout change)
 *   - Large-family optimisation via viewport culling (built into React Flow)
 */

import React, { memo, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState, forwardRef } from 'react';
import { useTranslation } from 'react-i18next';
import { AncestryFanChart } from './AncestryFanChart';
import ReactFlow, {
  Background,
  BackgroundVariant,
  MiniMap,
  type NodeTypes,
  type EdgeTypes,
  type NodeMouseHandler,
  type EdgeMouseHandler,
  type OnMove,
  type OnNodesChange,
  applyNodeChanges,
  SelectionMode,
  useReactFlow,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { PersonNode } from './nodes/PersonNode';
import { FamilyGroupNode } from './nodes/FamilyGroupNode';
import { ParentChildEdge } from './edges/ParentChildEdge';
import { UnionEdge } from './edges/UnionEdge';
import { TreeControls } from './controls/TreeControls';
import { useTreeLayout } from './useTreeLayout';
import { useExpandCollapse } from './useExpandCollapse';
import { ancestorSubgraphIds } from './algorithms/ancestorChart';
import { useCanvasStore } from '@store/canvas.store';
import { useThemeStore } from '@store/theme.store';
import type { ApiTreeGraph, TreeNode, TreeEdge, PersonNodeData } from '../types';
import { DEFAULT_LAYOUT_OPTIONS } from '../types';

// ── Ctrl+drag helper ───────────────────────────────────────────────────────

/**
 * BFS over familyGroups to collect every visible descendant node ID
 * (both FamilyGroup nodes and child Person nodes) below a given person.
 */
function getDescendantNodeIds(
  personId: string,
  graph: ApiTreeGraph,
  visibleIds: Set<string>,
): Set<string> {
  const result  = new Set<string>();
  const queue   = [personId];
  const seen    = new Set<string>();

  while (queue.length > 0) {
    const pid = queue.shift()!;
    if (seen.has(pid)) continue;
    seen.add(pid);

    for (const fg of graph.familyGroups) {
      if (!fg.parentIds.includes(pid)) continue;
      if (visibleIds.has(fg.id))   result.add(fg.id);

      for (const childId of Object.keys(fg.children)) {
        if (visibleIds.has(childId)) result.add(childId);
        queue.push(childId);
      }
    }
  }
  return result;
}


// ── Static maps ────────────────────────────────────────────────────────────

// ── Chart legend ──────────────────────────────────────────────────────────

function LegendRow({
  icon, label, count, color, textColor,
}: { icon: string; label: string; count: number; color: string; textColor: string }) {
  return (
    <div className="flex items-center gap-2">
      <span style={{ color, width: 14, textAlign: 'center', fontSize: 13, fontWeight: 700, lineHeight: 1 }}>
        {icon}
      </span>
      <span className="text-xs flex-1" style={{ color: textColor }}>{label}</span>
      <span className="text-xs font-bold tabular-nums" style={{ color: textColor }}>{count}</span>
    </div>
  );
}

import type { LayoutMode } from '../types';

const LEGEND_TITLE_KEYS: Record<LayoutMode, string> = {
  compact:             'legend.familyTree',
  generation:          'legend.familyTree',
  vertical:            'legend.familyTree',
  horizontal:          'legend.familyTree',
  fan:                 'legend.fanChart',
  'ancestry-fan':      'legend.ancestryFan',
  ancestor:            'legend.ancestorChart',
  descendant:          'legend.descendantChart',
  'descendant-family': 'legend.descendantsSpouses',
  'ancestor-family':   'legend.ancestorsSpouses',
  pedigree:            'legend.pedigreeChart',
};

function ChartLegend({
  graph,
  mode,
  visibleNodeIds,
}: {
  graph:          ApiTreeGraph;
  mode:           LayoutMode;
  /** IDs of all nodes currently rendered (persons + family groups). */
  visibleNodeIds: Set<string>;
}) {
  const { t } = useTranslation();
  const { stats, unionTypes, parentageTypes } = useMemo(() => {
    const people = graph.persons.filter((p) => visibleNodeIds.has(p.id));
    const families = graph.familyGroups.filter((fg) => visibleNodeIds.has(fg.id));

    const unions = new Set<string>();
    const parentages = new Set<string>();
    let hasDivorced = false;
    for (const fg of families) {
      unions.add(fg.unionType);
      if (fg.isDivorced) hasDivorced = true;
      for (const pt of Object.values(fg.children)) {
        parentages.add(pt);
      }
    }
    if (hasDivorced) unions.add('DIVORCED');

    return {
      stats: {
        total:   people.length,
        male:    people.filter((p) => p.sex === 'MALE').length,
        female:  people.filter((p) => p.sex === 'FEMALE').length,
        living:  people.filter((p) => p.isLiving).length,
        dead:    people.filter((p) => p.isDeceased).length,
      },
      unionTypes: unions,
      parentageTypes: parentages,
    };
  }, [graph, visibleNodeIds]);

  const theme = useThemeStore((s) => s.theme);

  if (stats.total === 0) return null;

  const hasUnions = unionTypes.size > 0;
  const hasChildren = parentageTypes.size > 0;

  return (
    <div
      className="backdrop-blur rounded-xl shadow-lg p-3 min-w-[160px]"
      style={{ background: theme.nodeBg, border: `1px solid ${theme.nodeBorder}` }}
    >
      <div className="flex items-center justify-between mb-2.5">
        <p
          className="text-[10px] font-semibold uppercase tracking-widest"
          style={{ color: theme.nodeSubtext }}
        >
          {t(LEGEND_TITLE_KEYS[mode])}
        </p>
        {/* Drag handle hint */}
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="ml-2 shrink-0" style={{ color: theme.nodeSubtext }}>
          <circle cx="4" cy="3" r="1" fill="currentColor"/>
          <circle cx="8" cy="3" r="1" fill="currentColor"/>
          <circle cx="4" cy="6" r="1" fill="currentColor"/>
          <circle cx="8" cy="6" r="1" fill="currentColor"/>
          <circle cx="4" cy="9" r="1" fill="currentColor"/>
          <circle cx="8" cy="9" r="1" fill="currentColor"/>
        </svg>
      </div>
      <div className="space-y-1.5">
        <LegendRow icon="#" label={t('legend.people')}   count={stats.total}  color={theme.nodeSubtext} textColor={theme.nodeText} />
        <div className="h-px my-1.5" style={{ background: theme.nodeBorder }} />
        <LegendRow icon="♂" label={t('legend.male')}     count={stats.male}   color="#3b82f6"            textColor={theme.nodeText} />
        <LegendRow icon="♀" label={t('legend.female')}   count={stats.female} color="#ec4899"            textColor={theme.nodeText} />
        <div className="h-px my-1.5" style={{ background: theme.nodeBorder }} />
        <LegendRow icon="●" label={t('legend.living')}   count={stats.living} color="#22c55e"            textColor={theme.nodeText} />
        <LegendRow icon="✝" label={t('legend.deceased')} count={stats.dead}   color={theme.nodeSubtext}  textColor={theme.nodeText} />
      </div>
      {(hasUnions || hasChildren) && (
        <div className="mt-2.5 pt-2 space-y-1.5" style={{ borderTop: `1px solid ${theme.nodeBorder}` }}>
          <p className="text-[9px] font-semibold uppercase tracking-widest mb-1" style={{ color: theme.nodeSubtext }}>{t('legend.lines')}</p>
          {hasUnions && (
            <>
              <p className="text-[8px] font-semibold uppercase tracking-widest mt-1 mb-0.5" style={{ color: theme.nodeSubtext }}>{t('legend.unions')}</p>
              {unionTypes.has('MARRIAGE') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="2" x2="24" y2="2" stroke="#f59e0b" strokeWidth="1.5"/><line x1="0" y1="6" x2="24" y2="6" stroke="#f59e0b" strokeWidth="1.5"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.marriage')}</span>
                </div>
              )}
              {unionTypes.has('PARTNERSHIP') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="4" x2="24" y2="4" stroke="#10b981" strokeWidth="1.5"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.partnership')}</span>
                </div>
              )}
              {unionTypes.has('COHABITATION') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="4" x2="24" y2="4" stroke="#6366f1" strokeWidth="1.5" strokeDasharray="6 6"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.cohabitation')}</span>
                </div>
              )}
              {unionTypes.has('DIVORCED') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="2" x2="24" y2="2" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="3 3"/><line x1="0" y1="6" x2="24" y2="6" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="3 3"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.divorced')}</span>
                </div>
              )}
            </>
          )}
          {hasChildren && (
            <>
              <p className="text-[8px] font-semibold uppercase tracking-widest mt-1.5 mb-0.5" style={{ color: theme.nodeSubtext }}>{t('legend.childrenSection')}</p>
              {parentageTypes.has('BIOLOGICAL') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="4" x2="24" y2="4" stroke={theme.edgeColor} strokeWidth="1.5"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.biological')}</span>
                </div>
              )}
              {parentageTypes.has('ADOPTIVE') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="4" x2="24" y2="4" stroke={theme.edgeColor} strokeWidth="1.5" strokeDasharray="6 3"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.adopted')}</span>
                </div>
              )}
              {parentageTypes.has('STEP') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="4" x2="24" y2="4" stroke={theme.edgeColor} strokeWidth="1.5" strokeDasharray="4 4"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.step')}</span>
                </div>
              )}
              {parentageTypes.has('FOSTER') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="4" x2="24" y2="4" stroke={theme.edgeColor} strokeWidth="1.5" strokeDasharray="6 3 2 3"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.foster')}</span>
                </div>
              )}
              {parentageTypes.has('UNKNOWN') && (
                <div className="flex items-center gap-2">
                  <svg width="24" height="8" className="shrink-0"><line x1="0" y1="4" x2="24" y2="4" stroke={theme.edgeColor} strokeWidth="1.5" strokeDasharray="4 4"/></svg>
                  <span className="text-[10px]" style={{ color: theme.nodeText }}>{t('legend.unknown')}</span>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── Draggable legend wrapper ──────────────────────────────────────────────
// Sits absolutely within the canvas container (outside the ReactFlow
// viewport transform) so it stays fixed on screen while panning/zooming.

function DraggableLegend({ children }: { children: React.ReactNode }) {
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null);
  const selfRef    = useRef<HTMLDivElement>(null);
  const isDragging = useRef(false);
  const origin     = useRef<{ mx: number; my: number; px: number; py: number } | null>(null);

  // Attach global move/up listeners once
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current || !origin.current) return;
      setDragPos({
        x: origin.current.px + e.clientX - origin.current.mx,
        y: origin.current.py + e.clientY - origin.current.my,
      });
    };
    const onUp = () => { isDragging.current = false; };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup',   onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup',   onUp);
    };
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    e.stopPropagation();   // prevent ReactFlow from starting a pan
    e.preventDefault();
    const el  = selfRef.current;
    const par = el?.offsetParent as HTMLElement | null;
    let px = dragPos?.x ?? 16;
    let py = dragPos?.y ?? 0;
    if (!dragPos && el && par) {
      // First drag: capture rendered position so transition is seamless
      const elR  = el.getBoundingClientRect();
      const parR = par.getBoundingClientRect();
      px = elR.left - parR.left;
      py = elR.top  - parR.top;
    }
    isDragging.current = true;
    origin.current     = { mx: e.clientX, my: e.clientY, px, py };
  }, [dragPos]);

  // Before first drag use CSS bottom/left so we don't need to know canvas height
  const posStyle: React.CSSProperties = dragPos
    ? { left: dragPos.x, top: dragPos.y }
    : { left: 16, bottom: 60 };

  return (
    <div
      ref={selfRef}
      data-pdf-legend
      className="cursor-grab active:cursor-grabbing"
      style={{ position: 'absolute', zIndex: 10, userSelect: 'none', ...posStyle }}
      onMouseDown={handleMouseDown}
    >
      {children}
    </div>
  );
}

// ── Ancestry fan chart node ────────────────────────────────────────────────
// Renders the full SVG fan chart as a single ReactFlow node so pan/zoom/
// minimap and all toolbar controls keep working normally.

interface FanNodeData { graph: ApiTreeGraph; focusPersonId: string }

const FanChartNode = memo(function FanChartNode({ data }: { data: FanNodeData }) {
  return (
    <AncestryFanChart
      graph={data.graph}
      focusPersonId={data.focusPersonId}
      maxGenerations={8}
    />
  );
});
FanChartNode.displayName = 'FanChartNode';

const NODE_TYPES: NodeTypes = {
  person: PersonNode,
  'family-group': FamilyGroupNode,
  'ancestry-fan': FanChartNode as any,
};

const EDGE_TYPES: EdgeTypes = {
  'parent-child': ParentChildEdge,
  union: UnionEdge,
};

const DEFAULT_VIEWPORT = { x: 0, y: 0, zoom: 0.8 };

// ── Lineage edge highlighting ──────────────────────────────────────────────

/**
 * Returns edge IDs for both the ancestor path (upward) and all descendant
 * paths (downward) from the selected person.
 */
function computeLineageEdgeIds(graph: ApiTreeGraph, selectedPersonId: string): Set<string> {
  const ids = new Set<string>();

  // ── Upward: trace through parent family groups to root ────────────
  const upQueue = [selectedPersonId];
  const upVisited = new Set<string>();

  while (upQueue.length > 0) {
    const personId = upQueue.shift()!;
    if (upVisited.has(personId)) continue;
    upVisited.add(personId);

    const fg = graph.familyGroups.find((g) => personId in g.children);
    if (!fg) continue;

    ids.add(`child-${fg.id}-${personId}`);
    for (const parentId of fg.parentIds) {
      ids.add(`union-${parentId}-${fg.id}`);
      upQueue.push(parentId);
    }
  }

  // ── Downward: trace through child family groups to leaves ─────────
  const downQueue = [selectedPersonId];
  const downVisited = new Set<string>();

  while (downQueue.length > 0) {
    const personId = downQueue.shift()!;
    if (downVisited.has(personId)) continue;
    downVisited.add(personId);

    const parentFgs = graph.familyGroups.filter((g) => g.parentIds.includes(personId));
    for (const fg of parentFgs) {
      // Highlight union edges for ALL parents in this group (the couple)
      for (const pid of fg.parentIds) {
        ids.add(`union-${pid}-${fg.id}`);
      }
      // Highlight parent-child edges and recurse into each child
      for (const childId of Object.keys(fg.children)) {
        ids.add(`child-${fg.id}-${childId}`);
        downQueue.push(childId);
      }
    }
  }

  return ids;
}

// ── Inner canvas ───────────────────────────────────────────────────────────

interface TreeCanvasInnerProps {
  graph: ApiTreeGraph | null;
  isLoading: boolean;
  onPersonSelect?: (personId: string) => void;
  onFamilyGroupSelect?: (familyGroupId: string) => void;
}

export interface TreeCanvasHandle {
  getPositions: () => Record<string, { x: number; y: number }>;
  loadPositions: (positions: Record<string, { x: number; y: number }>) => void;
  exportPdf: () => Promise<void>;
  scrollToNode: (personId: string) => void;
  refitView: () => void;
}

const TreeCanvasInner = forwardRef<TreeCanvasHandle, TreeCanvasInnerProps>(
function TreeCanvasInner({ graph, isLoading, onPersonSelect, onFamilyGroupSelect }, ref) {
  const { t } = useTranslation();
  const { fitView } = useReactFlow();
  const canvasTheme = useThemeStore((s) => s.theme);

  const layoutMode          = useCanvasStore((s) => s.layoutMode);
  const focusPersonId       = useCanvasStore((s) => s.focusPersonId);
  const selectedPersonId    = useCanvasStore((s) => s.selectedPersonId);
  const setSelectedPersonId = useCanvasStore((s) => s.setSelectedPersonId);
  const selectedEdge        = useCanvasStore((s) => s.selectedEdge);
  const setSelectedEdge     = useCanvasStore((s) => s.setSelectedEdge);
  const setZoom             = useCanvasStore((s) => s.setZoom);
  const setPan              = useCanvasStore((s) => s.setPan);
  const layoutResetKey      = useCanvasStore((s) => s.layoutResetKey);
  const isPdfMode           = useCanvasStore((s) => s.isPdfMode);

  const {
    expandedNodeIds,
    initializeExpanded,
    toggleExpand,
    expandAll,
    collapseAll,
  } = useExpandCollapse(graph);

  const setToggleExpand = useCanvasStore((s) => s.setToggleExpand);
  useEffect(() => { setToggleExpand(toggleExpand); }, [toggleExpand, setToggleExpand]);
  const setSetSelectedPersonId = useCanvasStore((s) => s.setSetSelectedPersonId);
  useEffect(() => { setSetSelectedPersonId(setSelectedPersonId); }, [setSelectedPersonId, setSetSelectedPersonId]);

  // Expand every branch immediately so the full tree is visible on open.
  // Driven by expandedNodeIds (not a mount-only ref) so it self-heals if the
  // canvas store gets reset out from under an already-loaded graph — e.g.
  // React StrictMode's dev-only double-invoke of FamilyTreePage's unmount
  // cleanup (resetCanvas) racing with this effect on a cached-data revisit.
  useEffect(() => {
    if (!graph || graph.persons.length === 0 || expandedNodeIds.size > 0) return;
    expandAll(graph);
    // Wait for ReactFlow to finish laying out all nodes before fitting
    setTimeout(() => fitView({ duration: 600, padding: 0.12 }), 150);
  }, [graph, expandedNodeIds, expandAll]); // eslint-disable-line react-hooks/exhaustive-deps

  const layoutOpts = useMemo(
    () => ({
      ...DEFAULT_LAYOUT_OPTIONS,
      mode: layoutMode,
      direction: layoutMode === 'horizontal' ? ('LR' as const) : ('TB' as const),
      focusPersonId: focusPersonId ?? undefined,
    }),
    [layoutMode, focusPersonId]
  );

  // ── Draggable node positions ───────────────────────────────────────────────
  //
  // displayNodes starts from the layout-computed positions and then diverges
  // as the user drags nodes. It resets to layout whenever the layout changes
  // (mode switch, expand/collapse, graph reload).

  const { nodes: layoutNodes, edges: rawEdges } = useTreeLayout(graph, expandedNodeIds, layoutOpts);

  // Highlight ancestor path when a person is selected; dim all other edges.
  // Also mark the currently selected edge so it renders with a selection style.
  const edges = useMemo((): TreeEdge[] => {
    let result: TreeEdge[] = rawEdges;
    if (selectedPersonId && graph) {
      const lineageIds = computeLineageEdgeIds(graph, selectedPersonId);
      if (lineageIds.size > 0) {
        result = result.map((e) => ({
          ...e,
          data: { ...e.data, isHighlighted: lineageIds.has(e.id) },
        })) as TreeEdge[];
      }
    }
    if (selectedEdge) {
      result = result.map((e) =>
        e.id === selectedEdge.id ? { ...e, selected: true } : e
      );
    }
    return result;
  }, [rawEdges, selectedPersonId, selectedEdge, graph]);

  const [displayNodes, setDisplayNodes] = useState<TreeNode[]>([]);
  const prevLayoutKey = useRef('');
  const containerRef  = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    getPositions: () =>
      Object.fromEntries(displayNodes.map((n) => [n.id, { x: n.position.x, y: n.position.y }])),
    loadPositions: (positions) => {
      setDisplayNodes((curr) =>
        curr.map((n) => ({ ...n, position: positions[n.id] ?? n.position }))
      );
      setTimeout(() => fitView({ duration: 500, padding: 0.15 }), 80);
    },
    scrollToNode: (personId) => {
      fitView({ nodes: [{ id: personId }], duration: 600, padding: 0.5, minZoom: 0.8, maxZoom: 1.5 });
    },
    refitView: () => {
      fitView({ duration: 500, padding: 0.15, minZoom: 0.05 });
    },
    exportPdf: async () => {
      if (!containerRef.current) return;
      const { toPng }          = await import('html-to-image');
      const { default: jsPDF } = await import('jspdf');

      const { layoutMode, focusPersonId, zoom, pan } = useCanvasStore.getState();

      // ── 1. Build title + filename ────────────────────────────────────────
      const focusPerson = graph?.persons.find((p) => p.id === focusPersonId);
      const focusName   = focusPerson
        ? [focusPerson.displayGivenName, focusPerson.displaySurname].filter(Boolean).join(' ')
        : '';
      const treeName = (graph as any)?.treeName ?? 'Family Tree';

      const PDF_TITLES: Record<LayoutMode, string> = {
        compact:             treeName,
        generation:          treeName,
        vertical:            treeName,
        horizontal:          treeName,
        fan:                 focusName ? `Fan Chart — ${focusName}` : 'Fan Chart',
        'ancestry-fan':      focusName ? `Ancestry Fan — ${focusName}` : 'Ancestry Fan',
        ancestor:            focusName ? `Ancestors of ${focusName}` : 'Ancestor Chart',
        descendant:          focusName ? `Descendants of ${focusName}` : 'Descendant Chart',
        'descendant-family': focusName ? `Descendants of ${focusName}` : 'Descendants + Spouses',
        'ancestor-family':   focusName ? `Ancestors of ${focusName}` : 'Ancestors + Spouses',
        pedigree:            focusName ? `Pedigree — ${focusName}` : 'Pedigree Chart',
      };
      const title    = PDF_TITLES[layoutMode] ?? treeName;
      const filename = title.replace(/[^\w\s\-]/g, '').replace(/\s+/g, '_') + '.pdf';

      const container = containerRef.current;
      const canvasW   = container.clientWidth;
      const canvasH   = container.clientHeight;

      // ── 2. Find emptiest quadrant for legend placement ───────────────────
      const quadCounts = { TL: 0, TR: 0, BL: 0, BR: 0 };
      for (const node of displayNodes) {
        if (node.type !== 'person') continue;
        const vx = node.position.x * zoom + pan.x;
        const vy = node.position.y * zoom + pan.y;
        if      (vx <  canvasW / 2 && vy <  canvasH / 2) quadCounts.TL++;
        else if (vx >= canvasW / 2 && vy <  canvasH / 2) quadCounts.TR++;
        else if (vx <  canvasW / 2 && vy >= canvasH / 2) quadCounts.BL++;
        else                                              quadCounts.BR++;
      }
      const emptiest = (Object.entries(quadCounts) as [string, number][])
        .sort((a, b) => a[1] - b[1])[0][0] as 'TL' | 'TR' | 'BL' | 'BR';
      const LM = 16;
      const legendPositions = {
        TL: { left: `${LM}px`, top: `${LM}px`,  right: 'auto', bottom: 'auto' },
        TR: { right: `${LM}px`, top: `${LM}px`, left: 'auto',  bottom: 'auto' },
        BL: { left: `${LM}px`, bottom: `${LM}px`, right: 'auto', top: 'auto' },
        BR: { right: `${LM}px`, bottom: `${LM}px`, left: 'auto', top: 'auto' },
      };
      const lPos = legendPositions[emptiest];

      // Reposition legend via DOM — no React re-render needed
      const legendEl     = container.querySelector('[data-pdf-legend]') as HTMLElement | null;
      const savedLegend  = legendEl?.style.cssText ?? '';
      if (legendEl) Object.assign(legendEl.style, lPos);

      // Hide React Flow chrome (attribution link / "↙" arrow)
      const attributionEl = container.querySelector('.react-flow__attribution') as HTMLElement | null;
      if (attributionEl) attributionEl.style.visibility = 'hidden';

      // ── 3. Switch to PDF render mode + capture ───────────────────────────
      // Zustand setState is synchronous; two rAF ticks let React flush + paint.
      useCanvasStore.getState().setIsPdfMode(true);
      await new Promise(requestAnimationFrame);
      await new Promise(requestAnimationFrame);

      let treeDataUrl: string;
      try {
        treeDataUrl = await toPng(container, {
          pixelRatio: 2,
          imagePlaceholder: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN88P/BfwAJhAPkE0NghgAAAABJRU5ErkJggg==',
          filter: (node: HTMLElement) => {
            if (node.classList?.contains('react-flow__attribution')) return false;
            return true;
          },
        });
      } finally {
        useCanvasStore.getState().setIsPdfMode(false);
        if (legendEl)     legendEl.style.cssText = savedLegend;
        if (attributionEl) attributionEl.style.visibility = '';
      }

      // ── 4. Build header strip (canvas API — pixel-perfect, no overlap) ───
      const pixelRatio  = 2;
      const HEADER_PX   = 60; // header height in canvas pixels
      const headerImgW  = Math.round(canvasW * pixelRatio);
      const headerImgH  = Math.round(HEADER_PX * pixelRatio);

      const hCanvas = document.createElement('canvas');
      hCanvas.width  = headerImgW;
      hCanvas.height = headerImgH;
      const ctx = hCanvas.getContext('2d')!;

      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, headerImgW, headerImgH);

      // Title — shrink font until it fits
      let fontSize = 22 * pixelRatio;
      ctx.font = `700 ${fontSize}px system-ui,-apple-system,sans-serif`;
      const maxTextW = headerImgW - 80 * pixelRatio;
      while (ctx.measureText(title).width > maxTextW && fontSize > 10 * pixelRatio) {
        fontSize -= pixelRatio;
        ctx.font = `700 ${fontSize}px system-ui,-apple-system,sans-serif`;
      }
      ctx.fillStyle   = '#1e293b';
      ctx.textAlign   = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(title, headerImgW / 2, headerImgH / 2);

      // Thin bottom separator
      ctx.strokeStyle = '#e2e8f0';
      ctx.lineWidth   = pixelRatio;
      ctx.beginPath();
      ctx.moveTo(30 * pixelRatio, headerImgH - 1);
      ctx.lineTo(headerImgW - 30 * pixelRatio, headerImgH - 1);
      ctx.stroke();

      const headerDataUrl = hCanvas.toDataURL('image/png');

      // ── 5. Assemble PDF ──────────────────────────────────────────────────
      const treeImg = new Image();
      treeImg.src = treeDataUrl;
      await new Promise<void>((r) => { treeImg.onload = () => r(); });

      const totalW = treeImg.naturalWidth;
      const totalH = treeImg.naturalHeight + headerImgH;

      const pdf = new jsPDF({
        orientation: totalW >= totalH ? 'landscape' : 'portrait',
        unit: 'px',
        format: [totalW, totalH],
      });
      pdf.addImage(headerDataUrl, 'PNG', 0, 0,           totalW, headerImgH);
      pdf.addImage(treeDataUrl,   'PNG', 0, headerImgH,  totalW, treeImg.naturalHeight);
      pdf.save(filename);
    },
  }), [displayNodes, fitView]);

  useEffect(() => {
    // Key covers structural changes: node added/removed or position moved by layout
    const key = layoutNodes.map((n) => `${n.id}:${n.position.x.toFixed(0)},${n.position.y.toFixed(0)}`).join('|');
    if (key !== prevLayoutKey.current) {
      // Structure changed — full reset (new/removed nodes, layout mode change, etc.)
      prevLayoutKey.current = key;
      setDisplayNodes(layoutNodes);
    } else {
      // Structure unchanged — only patch node data so edits (name, status, photo)
      // appear immediately without disturbing the user's manual drag positions
      const dataMap = new Map(layoutNodes.map((n) => [n.id, n.data]));
      setDisplayNodes((curr) =>
        curr.map((dn) => {
          const newData = dataMap.get(dn.id);
          return newData ? { ...dn, data: newData } : dn;
        }) as TreeNode[],
      );
    }
  }, [layoutNodes]);

  // Reset node positions only when the reset button is pressed (no fit view)
  useEffect(() => {
    if (layoutResetKey === 0) return; // skip the initial mount
    setDisplayNodes(layoutNodes);
  }, [layoutResetKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Forward React Flow's node changes (drag, selection, etc.) to displayNodes
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => setDisplayNodes((nds) => applyNodeChanges(changes, nds as any[]) as TreeNode[]),
    []
  );

  // ── Fit view on layout change ──────────────────────────────────────────────

  useEffect(() => {
    if (layoutNodes.length > 0) {
      setTimeout(() => fitView({ duration: 500, padding: 0.15 }), 50);
    }
  }, [layoutMode]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Event handlers ─────────────────────────────────────────────────────────

  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      setSelectedEdge(null);
      if (node.type === 'person') {
        setSelectedPersonId(node.id);
        onPersonSelect?.(node.id);
      } else if (node.type === 'family-group') {
        onFamilyGroupSelect?.(node.id);
      }
    },
    [setSelectedPersonId, setSelectedEdge, onPersonSelect, onFamilyGroupSelect]
  );

  const onEdgeClick: EdgeMouseHandler = useCallback(
    (_, edge) => {
      if (!edge.data) return;
      setSelectedPersonId(null);
      setSelectedEdge({
        id: edge.id,
        kind: edge.data.kind,
        source: edge.source,
        target: edge.target,
        unionType: edge.data.unionType,
        parentageType: edge.data.parentageType,
      });
    },
    [setSelectedPersonId, setSelectedEdge]
  );

  const onPaneClick = useCallback(() => {
    setSelectedPersonId(null);
    setSelectedEdge(null);
  }, [setSelectedPersonId, setSelectedEdge]);

  const onMoveEnd: OnMove = useCallback(
    (_, viewport) => {
      setZoom(viewport.zoom);
      setPan({ x: viewport.x, y: viewport.y });
    },
    [setZoom, setPan]
  );

  const handleExpandAll   = useCallback(() => { if (graph) expandAll(graph); }, [graph, expandAll]);
  const handleCollapseAll = useCallback(() => {
    if (focusPersonId) collapseAll(focusPersonId);
  }, [focusPersonId, collapseAll]);

  const miniMapNodeColor = useCallback((node: any) => {
    if (node.type === 'family-group') return '#e2e8f0';
    const colorMap: Record<string, string> = {
      MALE: '#3b82f6', FEMALE: '#ec4899', OTHER: '#8b5cf6', UNKNOWN: '#94a3b8',
    };
    return colorMap[node.data?.sex ?? 'UNKNOWN'] ?? '#94a3b8';
  }, []);

  // ── Ctrl+drag: move a person together with all visible descendants ─────────

  const ctrlDragRef = useRef<{
    anchorId: string;
    companionIds: Set<string>;
    lastPos: { x: number; y: number };
  } | null>(null);

  const [ctrlDragActive, setCtrlDragActive] = useState(false);
  const [ctrlDragNodeType, setCtrlDragNodeType] = useState<'person' | 'family-group'>('person');
  const [ctrlHeld, setCtrlHeld] = useState(false);

  useEffect(() => {
    const down = (e: KeyboardEvent) => { if (e.key === 'Control') setCtrlHeld(true);  };
    const up   = (e: KeyboardEvent) => { if (e.key === 'Control') setCtrlHeld(false); };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup',   up);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); };
  }, []);

  const onNodeDragStart: NodeMouseHandler = useCallback(
    (event, node) => {
      if (!(event as unknown as MouseEvent).ctrlKey || !graph) {
        ctrlDragRef.current = null;
        return;
      }
      const visibleIds = new Set(displayNodes.map((n) => n.id));
      let companionIds: Set<string>;

      if (node.type === 'person') {
        companionIds = getDescendantNodeIds(node.id, graph, visibleIds);
        setCtrlDragNodeType('person');
      } else if (node.type === 'family-group') {
        // Ring union drags alone — no members travel with it
        setCtrlDragNodeType('family-group');
        ctrlDragRef.current = null;
        return;
      } else {
        ctrlDragRef.current = null;
        return;
      }

      ctrlDragRef.current = {
        anchorId:    node.id,
        companionIds,
        lastPos:     { x: node.position.x, y: node.position.y },
      };
      if (companionIds.size > 0) setCtrlDragActive(true);
    },
    [graph, displayNodes],
  );

  const onNodeDrag: NodeMouseHandler = useCallback(
    (_, node) => {
      const drag = ctrlDragRef.current;
      if (!drag || node.id !== drag.anchorId) return;
      const dx = node.position.x - drag.lastPos.x;
      const dy = node.position.y - drag.lastPos.y;
      if (dx === 0 && dy === 0) return;
      drag.lastPos = { x: node.position.x, y: node.position.y };
      setDisplayNodes((nds) =>
        nds.map((n) =>
          drag.companionIds.has(n.id)
            ? { ...n, position: { x: n.position.x + dx, y: n.position.y + dy } }
            : n,
        ),
      );
    },
    [],
  );

  const onNodeDragStop: NodeMouseHandler = useCallback(() => {
    ctrlDragRef.current = null;
    setCtrlDragActive(false);
  }, []);

  // ── Ancestry fan chart node ───────────────────────────────────────────────
  // When in ancestry-fan mode, override displayNodes with a single custom node
  // that renders the SVG fan chart.  All ReactFlow infrastructure (pan, zoom,
  // minimap, toolbar) continues to work normally.

  const fanNode = useMemo(() => {
    if (layoutMode !== 'ancestry-fan' || !graph) return null;

    // Resolve focus person (same fallback logic as AncestryFanChart itself)
    const personSet = new Set(graph.persons.map((p) => p.id));
    let fid = focusPersonId ?? '';
    if (!fid || !personSet.has(fid)) {
      const childIds = new Set<string>();
      for (const fg of graph.familyGroups)
        for (const cId of Object.keys(fg.children))
          if (personSet.has(cId)) childIds.add(cId);
      fid = (graph.persons.find((p) => childIds.has(p.id)) ?? graph.persons[0])?.id ?? '';
    }

    const FOCUS_R = 80;
    const RING_W  = 110;
    const maxR    = FOCUS_R + 4 * RING_W;
    const viewW   = maxR * 2 + 40;
    const viewH   = maxR + FOCUS_R + 40;

    return {
      id:       '__ancestry-fan__',
      type:     'ancestry-fan',
      position: { x: -viewW / 2, y: -viewH / 2 },
      data:     { graph, focusPersonId: fid } satisfies FanNodeData,
      width:    viewW,
      height:   viewH,
      draggable:  false,
      selectable: false,
    } as unknown as TreeNode;
  }, [layoutMode, graph, focusPersonId]);

  const reactFlowNodes = useMemo(() => {
    const base = layoutMode === 'ancestry-fan' && fanNode ? [fanNode] : displayNodes;
    if (!ctrlHeld) return base;
    return base.map((n) => n.type === 'family-group' ? { ...n, draggable: true } : n);
  }, [layoutMode, fanNode, displayNodes, ctrlHeld]);
  const reactFlowEdges = layoutMode === 'ancestry-fan' ? [] : edges;

  // ── Render ─────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-surface-muted">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-slate-500">{t('legend.loadingTree')}</p>
        </div>
      </div>
    );
  }

  if (!graph || graph.persons.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-surface-muted">
        <div className="text-center">
          <div className="text-4xl mb-3">🌳</div>
          <p className="text-slate-700 font-medium">{t('legend.noPeopleYet')}</p>
          <p className="text-sm text-slate-500 mt-1">{t('legend.addPersonToStart')}</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full relative" style={{ background: canvasTheme.canvasBg }}>
      {!isPdfMode && (ctrlDragActive || ctrlHeld) && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 bg-brand-600 text-white text-xs font-medium px-3 py-1.5 rounded-full shadow-lg pointer-events-none select-none">
          {ctrlDragActive
            ? 'Ctrl drag · moving with descendants'
            : 'Ctrl · drag a union to move it'}
        </div>
      )}
      <ReactFlow
        nodes={reactFlowNodes}
        edges={reactFlowEdges}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onNodesChange={onNodesChange}
        onNodeClick={onNodeClick}
        onEdgeClick={onEdgeClick}
        onPaneClick={onPaneClick}
        onMoveEnd={onMoveEnd}
        onNodeDragStart={onNodeDragStart}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        defaultViewport={DEFAULT_VIEWPORT}
        minZoom={0.05}
        maxZoom={3}
        selectionMode={SelectionMode.Partial}
        fitView
        fitViewOptions={{ padding: 0.12, duration: 600, minZoom: 0.05 }}
        onlyRenderVisibleElements
        panOnScroll={false}
        zoomOnScroll
        zoomOnPinch
        panOnDrag
        selectNodesOnDrag={false}
        elevateNodesOnSelect
        nodesFocusable
        edgesFocusable
        nodesDraggable
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color={canvasTheme.canvasDot} />

        {!isPdfMode && (
          <MiniMap
            nodeColor={miniMapNodeColor}
            nodeStrokeWidth={0}
            maskColor="rgba(248,250,252,0.7)"
            className="!bottom-4 !right-4 !rounded-xl !border !border-slate-200 !shadow-card"
            pannable
            zoomable
          />
        )}

        {!isPdfMode && (
          <TreeControls
            graph={graph}
            onExpandAll={handleExpandAll}
            onCollapseAll={handleCollapseAll}
          />
        )}

        {!isPdfMode && (
          <div className="absolute bottom-4 left-4 z-10 text-xs text-slate-400 bg-white/80 px-2 py-1 rounded-lg border border-slate-200">
            {t('legend.peopleVisible', { total: graph.persons.length, visible: displayNodes.filter((n) => n.type === 'person').length })}
          </div>
        )}
      </ReactFlow>

      {/* Draggable legend — outside ReactFlow so it stays viewport-fixed
          while the canvas pans/zooms. Shown for every layout mode. */}
      {graph && (
        <DraggableLegend>
          <ChartLegend
            graph={graph}
            mode={layoutMode}
            visibleNodeIds={
              layoutMode === 'ancestry-fan' && fanNode
                ? ancestorSubgraphIds(graph, (fanNode.data as unknown as FanNodeData).focusPersonId, 8)
                : new Set(reactFlowNodes.map((n) => n.id))
            }
          />
        </DraggableLegend>
      )}
    </div>
  );
}); // end forwardRef TreeCanvasInner

// ── Exported wrapper ───────────────────────────────────────────────────────

export interface TreeCanvasProps {
  graph: ApiTreeGraph | null;
  isLoading?: boolean;
  onPersonSelect?: (personId: string) => void;
  onFamilyGroupSelect?: (familyGroupId: string) => void;
}

export const TreeCanvas = forwardRef<TreeCanvasHandle, TreeCanvasProps>(
  function TreeCanvas({ graph, isLoading = false, onPersonSelect, onFamilyGroupSelect }, ref) {
  return (
    <ReactFlowProvider>
      <TreeCanvasInner
        ref={ref}
        graph={graph}
        isLoading={isLoading}
        onPersonSelect={onPersonSelect}
        onFamilyGroupSelect={onFamilyGroupSelect}
      />
    </ReactFlowProvider>
  );
});

export default TreeCanvas;
