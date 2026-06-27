/**
 * TreeControls — floating toolbar for the canvas.
 *
 * Positioned top-left. Controls:
 *   - Zoom in / Zoom out / Fit view
 *   - Layout mode toggle (TB / LR / Fan / Ancestor / Descendant / …)
 *   - Expand all / Collapse all
 *   - Export (PNG)
 */

import React, { memo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useReactFlow } from 'reactflow';
import type { LayoutMode } from '../../types';
import { useCanvasStore } from '@store/canvas.store';

// ── Compact view icon (two parent cards → child card) ─────────────────────
const CompactViewIcon = () => (
  <svg width="14" height="12" viewBox="0 0 14 12" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
    <rect x="0.5" y="0.5" width="4" height="2.5" rx="0.5" />
    <rect x="9.5" y="0.5" width="4" height="2.5" rx="0.5" />
    <rect x="5"   y="9"   width="4" height="2.5" rx="0.5" />
    <line x1="2.5" y1="3"   x2="2.5" y2="5.5" />
    <line x1="11.5" y1="3"  x2="11.5" y2="5.5" />
    <line x1="2.5"  y1="5.5" x2="11.5" y2="5.5" />
    <line x1="7"    y1="5.5" x2="7"    y2="9" />
  </svg>
);

/**
 * DescendantFamilyIcon — focus person (●) at top branching down to two couple pairs (○━○).
 * Conveys "show all descendants with their spouses."
 */
const DescendantFamilyIcon = () => (
  <svg width="16" height="14" viewBox="0 0 16 14" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
    {/* Focus: solid filled circle at top center */}
    <circle cx="8" cy="2" r="1.8" fill="currentColor" stroke="none" />
    {/* Branch lines */}
    <line x1="8"    y1="3.8" x2="8"    y2="5.5" />
    <line x1="3.5"  y1="5.5" x2="12.5" y2="5.5" />
    <line x1="3.5"  y1="5.5" x2="3.5"  y2="7.5" />
    <line x1="12.5" y1="5.5" x2="12.5" y2="7.5" />
    {/* Left couple: two circles connected by dash */}
    <circle cx="1.8" cy="10.5" r="1.5" />
    <line   x1="3.3" y1="10.5" x2="4"   y2="10.5" />
    <circle cx="5.3" cy="10.5" r="1.5" />
    {/* Right couple: two circles connected by dash */}
    <circle cx="10"  cy="10.5" r="1.5" />
    <line   x1="11.5" y1="10.5" x2="12.2" y2="10.5" />
    <circle cx="13.7" cy="10.5" r="1.5" />
  </svg>
);

/**
 * AncestorFamilyIcon — two couple pairs (○━○) at top merging down to focus person (●).
 * Conveys "show all ancestors with their spouses."
 */
const AncestorFamilyIcon = () => (
  <svg width="16" height="14" viewBox="0 0 16 14" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
    {/* Left couple (top-left): two circles connected */}
    <circle cx="1.8" cy="3.5" r="1.5" />
    <line   x1="3.3" y1="3.5" x2="4"   y2="3.5" />
    <circle cx="5.3" cy="3.5" r="1.5" />
    {/* Right couple (top-right): two circles connected */}
    <circle cx="10"  cy="3.5" r="1.5" />
    <line   x1="11.5" y1="3.5" x2="12.2" y2="3.5" />
    <circle cx="13.7" cy="3.5" r="1.5" />
    {/* Merging lines down to focus */}
    <line x1="3.5"  y1="5"   x2="3.5"  y2="8.5" />
    <line x1="12.5" y1="5"   x2="12.5" y2="8.5" />
    <line x1="3.5"  y1="8.5" x2="12.5" y2="8.5" />
    <line x1="8"    y1="8.5" x2="8"    y2="10.2" />
    {/* Focus: solid filled circle at bottom */}
    <circle cx="8" cy="12" r="1.8" fill="currentColor" stroke="none" />
  </svg>
);

// ── Icon helpers (minimal inline SVGs) ────────────────────────────────────

const PlusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="7" y1="2" x2="7" y2="12" /><line x1="2" y1="7" x2="12" y2="7" />
  </svg>
);
const MinusIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="2" y1="7" x2="12" y2="7" />
  </svg>
);
const FitIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5">
    <rect x="1" y="1" width="12" height="12" rx="1" />
    <rect x="4" y="4" width="6" height="6" />
  </svg>
);

// ── Generation sort icon (pyramid: 1 node → 2 nodes → 3 nodes) ───────────
const GenerationSortIcon = () => (
  <svg width="14" height="13" viewBox="0 0 14 13" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round">
    {/* Generation 0: 1 node centred */}
    <rect x="4.5" y="0.5" width="5" height="2.5" rx="0.5" />
    {/* Branches down */}
    <line x1="5.5"  y1="3"   x2="3"    y2="5.5" />
    <line x1="8.5"  y1="3"   x2="11"   y2="5.5" />
    {/* Generation 1: 2 nodes */}
    <rect x="0.5"  y="5.5" width="5" height="2.5" rx="0.5" />
    <rect x="8.5"  y="5.5" width="5" height="2.5" rx="0.5" />
    {/* Branches down */}
    <line x1="3"    y1="8"   x2="2.5"  y2="10.5" />
    <line x1="11"   y1="8"   x2="11.5" y2="10.5" />
    {/* Generation 2: 2 nodes (one per branch) */}
    <rect x="0.5"  y="10.5" width="4" height="2" rx="0.5" />
    <rect x="9.5"  y="10.5" width="4" height="2" rx="0.5" />
  </svg>
);

// ── Layout mode buttons ────────────────────────────────────────────────────

type LayoutModeEntry =
  | { mode: LayoutMode; label: string; titleKey: string; icon?: never }
  | { mode: LayoutMode; icon: React.ReactNode; titleKey: string; label?: never };

const LAYOUT_MODES: LayoutModeEntry[] = [
  { mode: 'generation',         icon: <GenerationSortIcon />, titleKey: 'treeControls.generationSort' },
  { mode: 'vertical',           label: '↕',  titleKey: 'treeControls.vertical' },
  { mode: 'horizontal',         label: '↔',  titleKey: 'treeControls.horizontal' },
  { mode: 'ancestor',           label: '↑',  titleKey: 'treeControls.ancestor' },
  { mode: 'descendant',         label: '↓',  titleKey: 'treeControls.descendant' },
  { mode: 'descendant-family',  icon: <DescendantFamilyIcon />, titleKey: 'treeControls.descendantFamily' },
  { mode: 'ancestor-family',    icon: <AncestorFamilyIcon />,   titleKey: 'treeControls.ancestorFamily' },
  { mode: 'fan',                label: '◑',  titleKey: 'treeControls.fan' },
  { mode: 'ancestry-fan',       label: '◎',  titleKey: 'treeControls.ancestryFan' },
  { mode: 'pedigree',           label: '⊢',  titleKey: 'treeControls.pedigree' },
];

// ── Control button ─────────────────────────────────────────────────────────

interface CtrlBtnProps {
  onClick: () => void;
  title: string;
  active?: boolean;
  children: React.ReactNode;
}

const CtrlBtn = memo(({ onClick, title, active, children }: CtrlBtnProps) => (
  <button
    onClick={onClick}
    title={title}
    className={[
      'flex items-center justify-center w-8 h-8 rounded-lg text-sm font-medium transition-colors',
      active
        ? 'bg-brand-500 text-white shadow-sm'
        : 'bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-900 border border-slate-200',
    ].join(' ')}
  >
    {children}
  </button>
));
CtrlBtn.displayName = 'CtrlBtn';

// ── Divider ────────────────────────────────────────────────────────────────

const Divider = () => <div className="w-px h-6 bg-slate-200 mx-0.5" />;

// ── Main component ─────────────────────────────────────────────────────────

interface TreeControlsProps {
  graph: import('../../types').ApiTreeGraph | null;
  onExpandAll: () => void;
  onCollapseAll: () => void;
}

export const TreeControls = memo(({ graph, onExpandAll, onCollapseAll }: TreeControlsProps) => {
  const { t } = useTranslation();
  const { zoomIn, zoomOut, fitView } = useReactFlow();
  const layoutMode      = useCanvasStore((s) => s.layoutMode);
  const setLayoutMode   = useCanvasStore((s) => s.setLayoutMode);
  const zoom            = useCanvasStore((s) => s.zoom);
  const bumpLayoutReset = useCanvasStore((s) => s.bumpLayoutReset);

  const handleFitView = useCallback(() => {
    fitView({ duration: 400, padding: 0.1 });
  }, [fitView]);

  // Switching to any layout mode forces a full reset so dragged positions
  // are discarded and the tree realigns in generation hierarchy.
  const handleLayoutMode = useCallback((mode: LayoutMode) => {
    setLayoutMode(mode);
    bumpLayoutReset();
  }, [setLayoutMode, bumpLayoutReset]);

  const handleCompactView = useCallback(() => {
    handleLayoutMode('compact');
  }, [handleLayoutMode]);

  const handleZoomIn  = useCallback(() => zoomIn({ duration: 200 }),  [zoomIn]);
  const handleZoomOut = useCallback(() => zoomOut({ duration: 200 }), [zoomOut]);

  return (
    <div className="absolute top-4 left-4 z-10 flex items-center gap-1 p-1.5 bg-white/90 backdrop-blur rounded-xl border border-slate-200 shadow-card">
      {/* Zoom controls */}
      <CtrlBtn onClick={handleZoomOut} title={t('treeControls.zoomOut')}>
        <MinusIcon />
      </CtrlBtn>

      <span className="px-1.5 text-xs text-slate-500 font-mono min-w-[36px] text-center select-none">
        {Math.round(zoom * 100)}%
      </span>

      <CtrlBtn onClick={handleZoomIn} title={t('treeControls.zoomIn')}>
        <PlusIcon />
      </CtrlBtn>

      <CtrlBtn onClick={handleFitView} title={t('treeControls.fitView')}>
        <FitIcon />
      </CtrlBtn>

      <Divider />

      {/* Layout modes */}
      {LAYOUT_MODES.map(({ mode, titleKey, ...rest }) => (
        <CtrlBtn
          key={mode}
          onClick={() => handleLayoutMode(mode)}
          title={t(titleKey)}
          active={layoutMode === mode}
        >
          {'icon' in rest ? rest.icon : rest.label}
        </CtrlBtn>
      ))}

      <Divider />

      {/* Expand / Collapse */}
      <CtrlBtn onClick={onExpandAll} title={t('treeControls.expandAll')}>
        ⊞
      </CtrlBtn>
      <CtrlBtn onClick={onCollapseAll} title={t('treeControls.collapseAll')}>
        ⊟
      </CtrlBtn>

      <Divider />

      {/* Reset layout */}
      <CtrlBtn onClick={bumpLayoutReset} title={t('treeControls.resetLayout')}>
        ↺
      </CtrlBtn>

      {/* Compact family-tree view */}
      <CtrlBtn
        onClick={handleCompactView}
        title={t('treeControls.compactView')}
        active={layoutMode === 'compact'}
      >
        <CompactViewIcon />
      </CtrlBtn>

    </div>
  );
});
TreeControls.displayName = 'TreeControls';
