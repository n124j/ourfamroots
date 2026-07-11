/**
 * TextPedigreeView — ancestor pedigree rendered as a compact indented text tree.
 *
 * Same ancestor data as the "Pedigree" canvas layout, but drawn as connector-line
 * text rows (like a directory tree) instead of boxes + edges — far more compact,
 * so many more generations fit on screen at once.
 *
 * Click a name to re-root the tree on that person. Rows beyond the visible
 * generation count show a ▶ toggle to reveal that branch's parents on demand.
 */

import React, { memo, useEffect, useMemo, useState } from 'react';
import type { ApiTreeGraph, ApiPerson, Sex } from '@features/tree/types';
import { SEX_BORDER_COLOR } from '@features/tree/types';
import { useThemeStore } from '@store/theme.store';
import { useCanvasStore } from '@store/canvas.store';

const DEFAULT_GENERATIONS = 4;
const MIN_GENERATIONS = 2;
const MAX_GENERATIONS = 10;
const ROW_H = 26;
const INDENT = 22;

function parseYear(raw: unknown): number | undefined {
  if (raw == null) return undefined;
  const n = typeof raw === 'number' ? raw : parseInt(String(raw), 10);
  return !isNaN(n) && n > 100 ? n : undefined;
}

function lifespan(p: ApiPerson): string | null {
  const birth = parseYear(p.birthYear) ?? (p.birthDate ? parseYear(p.birthDate.slice(0, 4)) : undefined);
  const death = parseYear(p.deathYear) ?? (p.deathDate ? parseYear(p.deathDate.slice(0, 4)) : undefined);
  if (!birth && !death) return null;
  const b = birth ?? '?';
  const d = death ?? (p.isLiving ? 'living' : '?');
  return `${b}–${d}`;
}

function personName(p: ApiPerson | undefined): string {
  if (!p) return 'Unknown';
  return [p.displayGivenName, p.displaySurname].filter(Boolean).join(' ') || 'Unknown';
}

const SEX_SYMBOL: Record<Sex, string> = { MALE: '♂', FEMALE: '♀', OTHER: '⚧', UNKNOWN: '' };

interface Row {
  personId: string;
  prefix: string;
  isRoot: boolean;
  isLast: boolean;
  depth: number;
  hasParents: boolean;
  cutOff: boolean; // has parents but not shown at this depth (needs expand toggle)
}

function buildRows(
  personId: string,
  personParentFG: Map<string, string>,
  fgById: Map<string, ApiTreeGraph['familyGroups'][number]>,
  personById: Map<string, ApiPerson>,
  baseDepth: number,
  expandedIds: Set<string>,
  prefix: string,
  isRoot: boolean,
  isLast: boolean,
  depth: number,
  visited: Set<string>,
  out: Row[],
) {
  if (visited.has(personId)) return;
  visited.add(personId);

  const fgId = personParentFG.get(personId);
  const fg = fgId ? fgById.get(fgId) : undefined;
  const parentIds = fg ? fg.parentIds.filter((id) => personById.has(id)) : [];
  const hasParents = parentIds.length > 0;

  const withinBase = depth < baseDepth;
  const manuallyExpanded = expandedIds.has(personId);
  const shouldRecurse = hasParents && (withinBase || manuallyExpanded);
  const cutOff = hasParents && !shouldRecurse;

  out.push({ personId, prefix, isRoot, isLast, depth, hasParents, cutOff });

  if (shouldRecurse) {
    const childPrefix = isRoot ? '' : prefix + (isLast ? '    ' : '│   ');
    parentIds.forEach((pid, idx) => {
      buildRows(
        pid, personParentFG, fgById, personById, baseDepth, expandedIds,
        childPrefix, false, idx === parentIds.length - 1, depth + 1, visited, out,
      );
    });
  }
}

interface TextPedigreeViewProps {
  graph: ApiTreeGraph;
}

function TextPedigreeViewComponent({ graph }: TextPedigreeViewProps) {
  const theme = useThemeStore((s) => s.theme);
  const focusPersonId = useCanvasStore((s) => s.focusPersonId);
  const selectedPersonId = useCanvasStore((s) => s.selectedPersonId);
  const isPdfMode = useCanvasStore((s) => s.isPdfMode);

  const [baseDepth, setBaseDepth] = useState(DEFAULT_GENERATIONS);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  // Stack of previous roots, pushed each time a double-click re-roots the
  // tree, so "Back" can step out again instead of leaving no way home.
  const [history, setHistory] = useState<string[]>([]);

  // Switching trees entirely invalidates any in-progress back history.
  useEffect(() => { setHistory([]); }, [graph.treeId]);

  const personById = useMemo(() => new Map(graph.persons.map((p) => [p.id, p])), [graph.persons]);
  const fgById = useMemo(() => new Map(graph.familyGroups.map((fg) => [fg.id, fg])), [graph.familyGroups]);
  const personParentFG = useMemo(() => {
    const m = new Map<string, string>();
    for (const fg of graph.familyGroups) {
      for (const cId of Object.keys(fg.children)) m.set(cId, fg.id);
    }
    return m;
  }, [graph.familyGroups]);

  const rootId = useMemo(() => {
    if (focusPersonId && personById.has(focusPersonId)) return focusPersonId;
    const childIds = new Set(personParentFG.keys());
    return graph.persons.find((p) => childIds.has(p.id))?.id ?? graph.persons[0]?.id ?? null;
  }, [focusPersonId, personById, personParentFG, graph.persons]);

  // Re-rooting the tree resets any manual per-branch expansions from the old root.
  useEffect(() => { setExpandedIds(new Set()); }, [rootId]);

  const rows = useMemo(() => {
    if (!rootId) return [] as Row[];
    const out: Row[] = [];
    buildRows(rootId, personParentFG, fgById, personById, baseDepth, expandedIds, '', true, true, 0, new Set(), out);
    return out;
  }, [rootId, personParentFG, fgById, personById, baseDepth, expandedIds]);

  const rootPerson = rootId ? personById.get(rootId) : undefined;

  function handleSelect(personId: string) {
    useCanvasStore.getState().setSelectedPersonId(personId);
  }

  function handleRefocus(personId: string) {
    if (rootId && rootId !== personId) {
      setHistory((h) => [...h, rootId]);
    }
    useCanvasStore.getState().setFocusPersonId(personId);
    useCanvasStore.getState().setSelectedPersonId(personId);
  }

  function handleBack() {
    if (history.length === 0) return;
    const prev = history[history.length - 1];
    setHistory((h) => h.slice(0, -1));
    useCanvasStore.getState().setFocusPersonId(prev);
    useCanvasStore.getState().setSelectedPersonId(prev);
  }

  function toggleExpanded(personId: string) {
    setExpandedIds((curr) => {
      const next = new Set(curr);
      if (next.has(personId)) next.delete(personId); else next.add(personId);
      return next;
    });
  }

  if (!rootId) {
    return (
      <div className="w-full h-full flex items-center justify-center" style={{ background: theme.canvasBg }}>
        <p className="text-sm" style={{ color: theme.nodeSubtext }}>No people in this tree yet.</p>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col" style={{ background: theme.canvasBg }}>
      {!isPdfMode && (
        <div
          className="flex items-center gap-3 px-4 py-2.5 shrink-0"
          style={{ borderBottom: `1px solid ${theme.nodeBorder}`, background: theme.nodeBg }}
        >
          {history.length > 0 && (
            <button
              onClick={handleBack}
              title={`Back to ${personName(personById.get(history[history.length - 1]))}`}
              className="flex items-center gap-1 px-2 h-7 rounded-md text-xs font-medium border shrink-0"
              style={{ borderColor: theme.nodeBorder, color: theme.nodeText, background: theme.nodeBg }}
            >
              ← Back
            </button>
          )}
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-wide" style={{ color: theme.nodeSubtext }}>
              Text Pedigree
            </p>
            <p className="text-sm font-medium truncate" style={{ color: theme.nodeText }}>
              Ancestors of {personName(rootPerson)}
            </p>
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-1.5">
            <span className="text-xs" style={{ color: theme.nodeSubtext }}>Generations</span>
            <button
              onClick={() => setBaseDepth((d) => Math.max(MIN_GENERATIONS, d - 1))}
              className="w-6 h-6 rounded-md text-xs font-bold flex items-center justify-center border"
              style={{ borderColor: theme.nodeBorder, color: theme.nodeText, background: theme.nodeBg }}
              title="Fewer generations"
            >
              −
            </button>
            <span className="text-xs font-mono w-4 text-center" style={{ color: theme.nodeText }}>{baseDepth}</span>
            <button
              onClick={() => setBaseDepth((d) => Math.min(MAX_GENERATIONS, d + 1))}
              className="w-6 h-6 rounded-md text-xs font-bold flex items-center justify-center border"
              style={{ borderColor: theme.nodeBorder, color: theme.nodeText, background: theme.nodeBg }}
              title="More generations"
            >
              +
            </button>
          </div>
        </div>
      )}

      {/* PDF export needs the full unclipped content size — overflow:auto would
          otherwise cap the capture at whatever fits in the on-screen viewport. */}
      <div className={isPdfMode ? 'px-4 py-3' : 'flex-1 min-h-0 overflow-auto px-4 py-3'}>
        <div style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace' }}>
          {rows.map((row) => {
            const person = personById.get(row.personId);
            const name = personName(person);
            const sex = person?.sex ?? 'UNKNOWN';
            const color = SEX_BORDER_COLOR[sex];
            const life = person ? lifespan(person) : null;
            const isSelected = row.personId === selectedPersonId;
            const isFocusRoot = row.personId === rootId;
            const connector = row.isRoot ? '' : row.isLast ? '└── ' : '├── ';

            return (
              <div
                key={row.personId}
                className="flex items-center whitespace-pre rounded-md"
                style={{
                  height: ROW_H,
                  paddingLeft: 4,
                  background: isSelected ? theme.nodeHoverBg : 'transparent',
                }}
              >
                <span style={{ color: theme.nodeSubtext, opacity: 0.7 }}>{row.prefix}{connector}</span>
                <button
                  onClick={() => handleSelect(row.personId)}
                  onDoubleClick={() => handleRefocus(row.personId)}
                  title={`${name}${life ? ` (${life})` : ''} — double-click to explore their ancestors`}
                  className="hover:underline focus:outline-none"
                  style={{
                    color,
                    fontWeight: isFocusRoot ? 700 : 500,
                    textDecoration: isFocusRoot ? 'underline' : 'none',
                  }}
                >
                  {name}
                </button>
                {sex !== 'UNKNOWN' && (
                  <span className="ml-1 text-xs" style={{ color }}>{SEX_SYMBOL[sex]}</span>
                )}
                {life && (
                  <span className="ml-2 text-xs" style={{ color: theme.nodeSubtext }}>({life})</span>
                )}
                {row.cutOff && (
                  <button
                    onClick={() => toggleExpanded(row.personId)}
                    title="Show parents"
                    className="ml-1.5 text-xs leading-none"
                    style={{ color: theme.edgeHighlight }}
                  >
                    ▶
                  </button>
                )}
                {row.hasParents && !row.cutOff && expandedIds.has(row.personId) && (
                  <button
                    onClick={() => toggleExpanded(row.personId)}
                    title="Hide parents"
                    className="ml-1.5 text-xs leading-none"
                    style={{ color: theme.nodeSubtext }}
                  >
                    ◀
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {!isPdfMode && (
        <div
          className="px-4 py-1.5 text-[11px] shrink-0"
          style={{ borderTop: `1px solid ${theme.nodeBorder}`, color: theme.nodeSubtext, background: theme.nodeBg }}
        >
          Click a name to highlight it &middot; double-click to explore their ancestors &middot; ▶ reveals earlier generations &middot; use Back to return
        </div>
      )}
    </div>
  );
}

export const TextPedigreeView = memo(TextPedigreeViewComponent);
