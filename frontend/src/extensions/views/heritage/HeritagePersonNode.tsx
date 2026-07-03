/**
 * HeritagePersonNode — vintage parchment card with centered photo, serif text,
 * and sex symbols. Used by the Heritage view plugin.
 */

import React, { memo, useCallback, useState } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import type { PersonNodeData } from '@features/tree/types';
import {
  SEX_BORDER_COLOR,
  PERSON_NODE_WIDTH,
} from '@features/tree/types';
import { useCanvasStore } from '@store/canvas.store';
import type { CanvasTheme } from '@store/theme.store';
import { isPreset, presetDataUri } from '@features/tree/avatarPresets';

function formatYears(birthYear?: number, deathYear?: number, isLiving?: boolean): string {
  if (!birthYear && !deathYear) return '';
  const birth = birthYear ? `${birthYear}` : '?';
  if (isLiving) return `b. ${birth}`;
  const death = deathYear ? `${deathYear}` : '?';
  return `${birth} – ${death}`;
}

const ExpandButton = memo(({ direction, isExpanded, onClick }: {
  direction: 'up' | 'down'; isExpanded: boolean; onClick: (e: React.MouseEvent) => void;
}) => {
  const arrow = direction === 'down'
    ? isExpanded ? '▲' : '▼'
    : isExpanded ? '▼' : '▲';
  return (
    <button
      onClick={onClick}
      className="absolute flex items-center justify-center w-5 h-5 rounded-full bg-white border border-slate-300 text-slate-500 hover:bg-slate-50 hover:border-slate-400 transition-colors text-[9px] leading-none shadow-sm"
      style={{ [direction === 'down' ? 'bottom' : 'top']: -10, left: '50%', transform: 'translateX(-50%)' }}
      title={isExpanded ? 'Collapse' : 'Expand'}
    >
      {arrow}
    </button>
  );
});
ExpandButton.displayName = 'HeritageExpandButton';

function HeritagePersonNodeComponent(props: NodeProps<PersonNodeData> & { theme: CanvasTheme; isPdfMode?: boolean }) {
  const { data, selected, dragging, theme, isPdfMode } = props;
  const {
    personId, displayGivenName, displaySurname, sex,
    birthYear, deathYear, isLiving, isDeceased, photoUrl,
    isFocus, isExpanded, hasHiddenChildren, hasHiddenParents,
  } = data;

  const toggleExpand = useCanvasStore((s) => s.toggleExpand);
  const setSelected = useCanvasStore((s) => s.setSelectedPersonId);
  const [hovered, setHovered] = useState(false);

  const handleExpandDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation(); toggleExpand?.(personId, 'children');
  }, [personId, toggleExpand]);
  const handleExpandUp = useCallback((e: React.MouseEvent) => {
    e.stopPropagation(); toggleExpand?.(personId, 'parents');
  }, [personId, toggleExpand]);
  const handleClick = useCallback(() => setSelected(personId), [personId, setSelected]);

  const borderColor = SEX_BORDER_COLOR[sex];
  const fullName = [displayGivenName, displaySurname].filter(Boolean).join(' ') || 'Unknown';
  const years = formatYears(birthYear, deathYear, isLiving && !isDeceased);
  const sexSymbol = sex === 'MALE' ? '♂' : sex === 'FEMALE' ? '♀' : '';
  const sexColor = sex === 'MALE' ? '#4a7a9b' : sex === 'FEMALE' ? '#b05070' : theme.nodeSubtext;

  const resolvedUrl = photoUrl && isPreset(photoUrl) ? presetDataUri(photoUrl) : photoUrl;

  return (
    <>
      <Handle type="target" position={Position.Top} className="!opacity-0 !pointer-events-none" />
      <div style={{ width: PERSON_NODE_WIDTH, position: 'relative' }}>
        {!isPdfMode && hasHiddenParents && <ExpandButton direction="up" isExpanded={isExpanded} onClick={handleExpandUp} />}
        <div
          onClick={isPdfMode ? undefined : handleClick}
          onMouseEnter={isPdfMode ? undefined : () => setHovered(true)}
          onMouseLeave={isPdfMode ? undefined : () => setHovered(false)}
          title={isPdfMode ? undefined : fullName}
          style={{
            width: PERSON_NODE_WIDTH, minHeight: 140, position: 'relative',
            cursor: isPdfMode ? 'default' : dragging ? 'grabbing' : 'grab',
            transform: !isPdfMode && dragging ? 'scale(1.04)' : 'scale(1)',
            transition: isPdfMode ? undefined : 'transform 0.3s ease, box-shadow 0.25s ease',
            zIndex: !isPdfMode && dragging ? 999 : undefined,
          }}
        >
          <div style={{
            width: '100%', minHeight: 140,
            background: isPdfMode ? theme.nodeBg : hovered ? theme.nodeHoverBg : theme.nodeBg,
            border: selected ? `2.5px solid ${borderColor}` : isFocus ? `2.5px solid ${borderColor}` : `1.5px solid ${theme.nodeBorder}`,
            borderRadius: 10,
            boxShadow: isPdfMode
              ? (isFocus ? `0 0 0 2px ${borderColor}44` : '0 1px 3px rgba(0,0,0,0.08)')
              : selected
                ? `0 0 0 3px ${borderColor}33, 0 4px 16px rgba(0,0,0,0.15)`
                : dragging ? '0 12px 32px rgba(0,0,0,0.25)' : '0 2px 8px rgba(0,0,0,0.1)',
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            padding: '12px 10px 10px', gap: 6,
          }}>
            {/* Photo frame */}
            <div style={{
              width: 64, height: 64, borderRadius: 6,
              border: `2px solid ${theme.nodeBorder}`,
              overflow: 'hidden', background: theme.canvasBg,
              boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.12)', flexShrink: 0,
            }}>
              {resolvedUrl ? (
                <img src={resolvedUrl} alt="" crossOrigin="anonymous"
                  style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: 'top', filter: 'sepia(30%) contrast(1.05)' }}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
              ) : (
                <div style={{
                  width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: theme.nodeSubtext, fontSize: 22, fontWeight: 600, fontFamily: 'Georgia, serif',
                }}>
                  {[displayGivenName[0], displaySurname[0]].filter(Boolean).join('').toUpperCase() || '?'}
                </div>
              )}
            </div>
            {/* Name */}
            <div style={{
              textAlign: 'center', fontFamily: 'Georgia, "Times New Roman", serif',
              fontWeight: 600, fontSize: 12, lineHeight: 1.3, color: theme.nodeText,
              maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>
              {fullName}
            </div>
            {/* Sex + years */}
            {(sexSymbol || years) && (
              <div style={{
                textAlign: 'center', fontSize: 11, color: theme.nodeSubtext,
                fontFamily: 'Georgia, serif', display: 'flex', alignItems: 'center', gap: 4,
              }}>
                {sexSymbol && <span style={{ color: sexColor, fontSize: 13 }}>{sexSymbol}</span>}
                {years && <span>{years}</span>}
              </div>
            )}
            {isFocus && !isPdfMode && (
              <div style={{
                fontSize: 9, fontWeight: 600, color: borderColor,
                background: `${borderColor}15`, padding: '1px 6px', borderRadius: 3,
                fontFamily: 'Georgia, serif',
              }}>Focus</div>
            )}
          </div>
        </div>
        {!isPdfMode && hasHiddenChildren && <ExpandButton direction="down" isExpanded={isExpanded} onClick={handleExpandDown} />}
      </div>
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !pointer-events-none" />
    </>
  );
}

export const HeritagePersonNode = memo(HeritagePersonNodeComponent);
HeritagePersonNode.displayName = 'HeritagePersonNode';
