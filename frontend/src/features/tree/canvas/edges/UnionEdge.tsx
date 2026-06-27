/**
 * UnionEdge — edge from a PersonNode (parent) to a FamilyGroupNode.
 *
 * Visual styles by union type:
 *   MARRIAGE     ════  double line (SVG trick: two strokes)
 *   PARTNERSHIP  ────  single solid
 *   COHABITATION ╌╌╌╌  dashed
 *   UNKNOWN      ┄┄┄┄  dotted
 *
 * A label appears when the person has multiple unions of the same type
 * (e.g. "1st Marriage", "2nd Marriage").  If a custom_label is set on the
 * family group it is shown instead.  Double-clicking the label lets the user
 * rename it to any freeform text (saved to family_groups.custom_label).
 */

import React, { memo, useRef, useState } from 'react';
import {
  EdgeLabelRenderer,
  getStraightPath,
  type EdgeProps,
} from 'reactflow';
import { useQueryClient } from '@tanstack/react-query';
import type { UnionEdgeData } from '../../types';
import { UNION_STROKE } from '../../types';
import { useThemeStore } from '@store/theme.store';
import { useCanvasStore } from '@store/canvas.store';
import { useAuthStore } from '@store/auth.store';
import { queryKeys } from '@queries/keys';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

const UNION_COLORS: Record<UnionEdgeData['unionType'], string> = {
  MARRIAGE: '#f59e0b',
  PARTNERSHIP: '#10b981',
  COHABITATION: '#6366f1',
  UNKNOWN: '#94a3b8',
};

const UNION_TYPE_LABEL: Record<UnionEdgeData['unionType'], string> = {
  MARRIAGE: 'Marriage',
  PARTNERSHIP: 'Partnership',
  COHABITATION: 'Cohabitation',
  UNKNOWN: 'Union',
};

function ordinalSuffix(n: number): string {
  if (n === 1) return '1st';
  if (n === 2) return '2nd';
  if (n === 3) return '3rd';
  return `${n}th`;
}

function UnionEdgeComponent({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  selected,
  target: familyGroupId,
}: EdgeProps<UnionEdgeData>) {
  const edgeWidth   = useThemeStore((s) => s.theme.edgeWidth);
  const treeId      = useCanvasStore((s) => s.treeId);
  const token       = useAuthStore((s) => s.accessToken);
  const queryClient = useQueryClient();

  const unionType   = data?.unionType ?? 'UNKNOWN';
  const isDivorced  = data?.isDivorced ?? false;
  const color       = selected ? '#f97316' : isDivorced ? '#94a3b8' : UNION_COLORS[unionType];
  const dashArray   = UNION_STROKE[unionType];
  const isSolid     = dashArray === 'solid';
  const isMarriage  = unionType === 'MARRIAGE';

  const hl      = data?.isHighlighted;
  const opacity = selected ? 1 : hl === true ? 1 : hl === false ? 0.15 : 1;
  const strokeW = selected ? edgeWidth * 2.5 : hl === true ? edgeWidth * 1.6 : edgeWidth;

  const ordinal      = data?.unionOrdinal;
  const customLabel  = data?.customLabel;
  // The visible label: custom takes priority, then ordinal (shown for all when multiple exist), then nothing
  const displayLabel = customLabel ?? (
    ordinal != null ? `${ordinalSuffix(ordinal)} ${UNION_TYPE_LABEL[unionType]}` : undefined
  );
  // Only show the label (and allow editing) when there is something to show
  const hasLabel = displayLabel != null;

  const [isEditing, setIsEditing] = useState(false);
  const [draft,     setDraft]     = useState('');
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  function openEditor(e: React.MouseEvent) {
    e.stopPropagation();
    setDraft(customLabel ?? '');
    setSaveError('');
    setIsEditing(true);
    // Focus the input after React renders it
    setTimeout(() => inputRef.current?.select(), 0);
  }

  async function commitEdit() {
    if (!treeId || !familyGroupId) { setIsEditing(false); return; }
    const trimmed = draft.trim();
    // No change → just close
    if (trimmed === (customLabel ?? '')) { setIsEditing(false); return; }

    setSaving(true);
    setSaveError('');
    try {
      const res = await fetch(`${API_BASE}/trees/${treeId}/family-groups/${familyGroupId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({ custom_label: trimmed || null }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setSaveError((d as any).detail ?? `Error ${res.status}`);
        return;
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.trees.detail(treeId) });
      setIsEditing(false);
    } catch (err: any) {
      setSaveError(err?.message ?? 'Network error');
    } finally {
      setSaving(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter')  { e.preventDefault(); commitEdit(); }
    if (e.key === 'Escape') { setIsEditing(false); }
  }

  const [edgePath, labelX, labelY] = getStraightPath({ sourceX, sourceY, targetX, targetY });
  const glowFilter = selected ? 'drop-shadow(0 0 4px #f97316aa)' : undefined;
  const labelColor = selected ? '#f97316' : color;

  // ── Shared label renderer ─────────────────────────────────────────────────
  function renderLabel(x: number, y: number) {
    if (!hasLabel && !isEditing) return null;

    return (
      <EdgeLabelRenderer>
        <div
          className="absolute pointer-events-none"
          style={{ transform: `translate(-50%, -50%) translate(${x}px,${y}px)` }}
        >
          {isEditing ? (
            <div className="pointer-events-auto flex flex-col items-center gap-1" style={{ minWidth: 90 }}>
              <input
                ref={inputRef}
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKeyDown}
                onBlur={commitEdit}
                disabled={saving}
                maxLength={200}
                placeholder={displayLabel ?? 'Custom label…'}
                className="text-[9px] font-semibold rounded border shadow-md bg-white outline-none px-1 py-0.5 w-28"
                style={{ borderColor: labelColor, color: labelColor }}
              />
              {saveError && (
                <span className="text-[8px] text-red-500 bg-white/90 rounded px-1 whitespace-nowrap pointer-events-none">
                  {saveError}
                </span>
              )}
            </div>
          ) : (
            <span
              className="pointer-events-auto px-1 py-0.5 text-[9px] font-semibold rounded border shadow-sm whitespace-nowrap select-none cursor-default"
              style={{
                background: selected ? '#fff7ed' : '#fffbeb',
                borderColor: labelColor,
                color: labelColor,
                filter: glowFilter,
              }}
              onDoubleClick={openEditor}
              title="Double-click to rename"
            >
              {displayLabel}
            </span>
          )}
        </div>
      </EdgeLabelRenderer>
    );
  }

  const divorcedDash = '4 4';

  const fmtDateShort = (iso?: string) => {
    if (!iso) return null;
    try { return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }); }
    catch { return iso; }
  };

  const tooltipTitle = displayLabel ?? UNION_TYPE_LABEL[unionType];
  const tooltipParts: string[] = [
    isDivorced ? `${tooltipTitle} (Divorced)` : tooltipTitle,
  ];
  const startStr = fmtDateShort(data?.unionDate) ?? (data?.unionDateYear != null ? String(data.unionDateYear) : null);
  const endStr = fmtDateShort(data?.unionEndDate) ?? (data?.unionEndDateYear != null ? String(data.unionEndDateYear) : null);
  if (startStr) tooltipParts.push(`Since: ${startStr}`);
  if (endStr)   tooltipParts.push(`Until: ${endStr}`);
  const tooltip = tooltipParts.join('\n');

  // ── Marriage: double line (dotted when divorced) ─────────────────────────
  if (isMarriage) {
    const lineOffset = selected ? 2.5 : hl === true ? 2 : 1.5;
    const [pathA] = getStraightPath({ sourceX: sourceX - lineOffset, sourceY, targetX: targetX - lineOffset, targetY });
    const [pathB] = getStraightPath({ sourceX: sourceX + lineOffset, sourceY, targetX: targetX + lineOffset, targetY });
    const midX = (sourceX + targetX) / 2;
    const midY = (sourceY + targetY) / 2;

    return (
      <>
        <g style={{ opacity, transition: 'opacity 0.25s', filter: glowFilter }}>
          <title>{tooltip}</title>
          <path d={pathA} stroke={color} strokeWidth={strokeW} strokeDasharray={isDivorced ? divorcedDash : undefined} fill="none" style={{ transition: 'stroke-width 0.25s' }} />
          <path d={pathB} stroke={color} strokeWidth={strokeW} strokeDasharray={isDivorced ? divorcedDash : undefined} fill="none" style={{ transition: 'stroke-width 0.25s' }} />
          {/* Wider invisible hit area for hover tooltip */}
          <path d={edgePath} stroke="transparent" strokeWidth={Math.max(strokeW * 6, 12)} fill="none" />
        </g>
        {renderLabel(midX, midY)}
      </>
    );
  }

  // ── Other union types: single line (dotted when divorced) ─────────────────
  return (
    <>
      <g style={{ opacity, transition: 'opacity 0.25s' }}>
        <title>{tooltip}</title>
        <path
          id={id}
          d={edgePath}
          stroke={color}
          strokeWidth={strokeW}
          strokeDasharray={isDivorced ? divorcedDash : (isSolid ? undefined : dashArray)}
          fill="none"
          style={{
            transition: 'stroke-width 0.25s',
            filter: glowFilter,
          }}
        />
        {/* Wider invisible hit area for hover tooltip */}
        <path d={edgePath} stroke="transparent" strokeWidth={Math.max(strokeW * 6, 12)} fill="none" />
      </g>
      {renderLabel(labelX, labelY)}
    </>
  );
}

export const UnionEdge = memo(UnionEdgeComponent);
UnionEdge.displayName = 'UnionEdge';
export default UnionEdge;
