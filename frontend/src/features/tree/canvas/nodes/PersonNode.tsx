/**
 * PersonNode — custom React Flow node for a single person.
 *
 * Visual anatomy (collapsed):
 *   ┌────────────────────────────┐  ← sex-coded border
 *   │ [Avatar]  Name             │
 *   │           1920 – 2005      │
 *   │                   [details▾]│
 *   └────────────────────────────┘
 *
 * When [details▾] is clicked an overlay panel appears directly below the card
 * showing full birth/death dates and social profile links.  The panel is
 * positioned absolutely so the layout algorithm is never affected.
 *
 * PDF mode (isPdfMode=true): expand buttons and details toggle are hidden;
 * given name and surname are each shown on their own line with no truncation.
 */

import React, { memo, useCallback, useState } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { useTranslation } from 'react-i18next';
import type { PersonNodeData } from '../../types';
import {
  SEX_BORDER_COLOR,
  SEX_BG_COLOR,
  PERSON_NODE_WIDTH,
  PERSON_NODE_HEIGHT,
} from '../../types';
import { useCanvasStore } from '@store/canvas.store';
import { useThemeStore } from '@store/theme.store';
import { isPreset, presetDataUri } from '../../avatarPresets';

// ── Avatar ─────────────────────────────────────────────────────────────────

interface AvatarProps {
  photoUrl?: string;
  givenName: string;
  surname: string;
  sex: PersonNodeData['sex'];
  size?: number;
}

const Avatar = memo(({ photoUrl, givenName, surname, sex, size = 44 }: AvatarProps) => {
  const initials = [givenName[0], surname[0]].filter(Boolean).join('').toUpperCase() || '?';
  const bg = SEX_BORDER_COLOR[sex];
  const resolvedUrl = photoUrl && isPreset(photoUrl) ? presetDataUri(photoUrl) : photoUrl;
  const [imgFailed, setImgFailed] = React.useState(false);
  return (
    <div
      className="flex-shrink-0 rounded-full overflow-hidden flex items-center justify-center text-white font-semibold select-none"
      style={{ width: size, height: size, background: bg, fontSize: size * 0.36 }}
    >
      {resolvedUrl && !imgFailed ? (
        <img
          src={resolvedUrl}
          alt=""
          crossOrigin="anonymous"
          className="w-full h-full object-cover object-top"
          onError={() => setImgFailed(true)}
        />
      ) : initials}
    </div>
  );
});
Avatar.displayName = 'Avatar';

// ── Expand / Collapse button (parents / children) ──────────────────────────

interface ExpandButtonProps {
  direction: 'up' | 'down';
  isExpanded: boolean;
  onClick: (e: React.MouseEvent) => void;
}

const ExpandButton = memo(({ direction, isExpanded, onClick }: ExpandButtonProps) => {
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
ExpandButton.displayName = 'ExpandButton';

// ── Date helpers ───────────────────────────────────────────────────────────

function formatYears(birthYear?: number, deathYear?: number, isLiving?: boolean): string {
  if (!birthYear && !deathYear) return '';
  const birth = birthYear ? `${birthYear}` : '?';
  if (isLiving) return `b. ${birth}`;
  const death = deathYear ? `${deathYear}` : '?';
  return `${birth} – ${death}`;
}

function formatFullDate(iso?: string): string {
  if (!iso) return '';
  try {
    return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, {
      year: 'numeric', month: 'long', day: 'numeric',
    });
  } catch {
    return iso;
  }
}

// ── Details overlay panel ──────────────────────────────────────────────────

interface DetailsRow {
  icon: React.ReactNode;
  label: string;
  value: string;
  href?: string;
}

interface DetailsPanelProps {
  data: PersonNodeData;
  borderColor: string;
  bg: string;
  textColor: string;
  subtextColor: string;
  borderCss: string;
}

function DetailsPanel({ data, borderColor, bg, textColor, subtextColor, borderCss }: DetailsPanelProps) {
  const rows: DetailsRow[] = [];

  if (data.birthDate || data.birthYear) {
    rows.push({
      icon: <span style={{ color: '#22c55e' }}>●</span>,
      label: 'Born',
      value: data.birthDate ? formatFullDate(data.birthDate) : `${data.birthYear}`,
    });
  }

  if (data.isDeceased || data.deathDate || data.deathYear) {
    rows.push({
      icon: <span style={{ color: subtextColor }}>✝</span>,
      label: 'Died',
      value: data.deathDate
        ? formatFullDate(data.deathDate)
        : data.deathYear
        ? `${data.deathYear}`
        : 'Unknown',
    });
  }

  if (data.bornCity || data.bornCountry) {
    rows.push({
      icon: <span style={{ color: '#22c55e', fontSize: 10 }}>📍</span>,
      label: 'Born in',
      value: [data.bornCity, data.bornCountry].filter(Boolean).join(', '),
    });
  }
  if (data.diedCity || data.diedCountry) {
    rows.push({
      icon: <span style={{ color: subtextColor, fontSize: 10 }}>📍</span>,
      label: 'Buried',
      value: [data.diedCity, data.diedCountry].filter(Boolean).join(', '),
    });
  }
  if (data.notes) {
    rows.push({
      icon: <span style={{ color: subtextColor, fontSize: 10 }}>📝</span>,
      label: 'Notes',
      value: data.notes,
    });
  }

  if (rows.length === 0) {
    return (
      <div
        className="rounded-b-xl px-3 py-2 text-center"
        style={{ background: bg, border: `1px solid ${borderCss}`, borderTop: 'none' }}
      >
        <span className="text-[10px]" style={{ color: subtextColor }}>No additional details</span>
      </div>
    );
  }

  return (
    <div
      className="rounded-b-xl overflow-hidden"
      style={{ background: bg, border: `1px solid ${borderCss}`, borderTop: 'none' }}
    >
      {rows.map((row, i) => (
        <div
          key={i}
          className="flex items-center gap-2 px-3 py-1.5"
          style={{ borderTop: i > 0 ? `1px solid ${borderCss}` : undefined }}
        >
          <span className="w-4 text-center flex-shrink-0 leading-none">{row.icon}</span>
          <span className="text-[10px] font-medium flex-shrink-0" style={{ color: subtextColor, minWidth: 42 }}>
            {row.label}
          </span>
          {row.href ? (
            <a
              href={row.href}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-[10px] truncate hover:underline"
              style={{ color: borderColor, maxWidth: 110 }}
              title={row.value}
            >
              {row.value}
            </a>
          ) : (
            <span className="text-[10px] truncate" style={{ color: textColor, maxWidth: 120 }} title={row.value}>
              {row.value}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

function PersonNodeComponent({ data, selected, dragging }: NodeProps<PersonNodeData>) {
  const { t } = useTranslation();
  const {
    personId,
    displayGivenName,
    displaySurname,
    sex,
    birthYear,
    deathYear,
    isLiving,
    isDeceased,
    photoUrl,
    isFocus,
    isExpanded,
    hasHiddenChildren,
    hasHiddenParents,
    bornCity,
    bornCountry,
    diedCity,
    diedCountry,
    notes,
    birthDate,
    deathDate,
  } = data;

  const toggleExpand  = useCanvasStore((s) => s.toggleExpand);
  const setSelected   = useCanvasStore((s) => s.setSelectedPersonId);
  const isPdfMode     = useCanvasStore((s) => s.isPdfMode);
  const theme         = useThemeStore((s) => s.theme);
  const [hovered,     setHovered]     = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const hasDetails = !!(birthDate || deathDate || bornCity || bornCountry || diedCity || diedCountry || notes
    || (isDeceased && !deathYear && !deathDate));

  const handleExpandDown = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    toggleExpand?.(personId, 'children');
  }, [personId, toggleExpand]);

  const handleExpandUp = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    toggleExpand?.(personId, 'parents');
  }, [personId, toggleExpand]);

  const handleClick = useCallback(() => setSelected(personId), [personId, setSelected]);

  const handleDetailsToggle = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setDetailsOpen((v) => !v);
  }, []);

  const borderColor = SEX_BORDER_COLOR[sex];
  const cardBg = theme.preset === 'classic'
    ? (hovered ? theme.nodeHoverBg : SEX_BG_COLOR[sex])
    : (hovered ? theme.nodeHoverBg : theme.nodeBg);
  const fullName = [displayGivenName, displaySurname].filter(Boolean).join(' ') || 'Unknown';
  const years = formatYears(birthYear, deathYear, isLiving && !isDeceased);
  const borderCss = selected ? borderColor : isFocus ? borderColor : theme.nodeBorder;

  // ── PDF mode: full names on two lines, no interactive chrome ─────────────
  if (isPdfMode) {
    return (
      <>
        <Handle type="target" position={Position.Top} className="!opacity-0 !pointer-events-none" />
        <div style={{ width: PERSON_NODE_WIDTH, position: 'relative' }}>
          <div
            style={{
              width: PERSON_NODE_WIDTH,
              minHeight: PERSON_NODE_HEIGHT,
              position: 'relative',
            }}
          >
            <div
              className="w-full rounded-xl flex items-center gap-3 px-3 py-3"
              style={{
                minHeight: PERSON_NODE_HEIGHT,
                background: cardBg,
                border: `2px solid ${borderCss}`,
                boxShadow: isFocus ? `0 0 0 2px ${borderColor}44` : '0 1px 3px rgba(0,0,0,0.08)',
              }}
            >
              {/* Left accent bar */}
              <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r" style={{ background: borderColor }} />

              <Avatar photoUrl={photoUrl} givenName={displayGivenName} surname={displaySurname} sex={sex} size={40} />

              {/* Name section — two lines, no truncation */}
              <div className="flex-1 min-w-0">
                {displayGivenName && (
                  <div
                    className="font-semibold leading-snug"
                    style={{ color: theme.nodeText, fontSize: 13, wordBreak: 'break-word' }}
                  >
                    {displayGivenName}
                  </div>
                )}
                {displaySurname && (
                  <div
                    className="font-semibold leading-snug"
                    style={{ color: theme.nodeText, fontSize: 13, wordBreak: 'break-word' }}
                  >
                    {displaySurname}
                  </div>
                )}
                {!displayGivenName && !displaySurname && (
                  <div className="font-semibold text-sm leading-tight" style={{ color: theme.nodeText }}>
                    Unknown
                  </div>
                )}
                {years && (
                  <div className="text-xs mt-0.5" style={{ color: theme.nodeSubtext }}>{years}</div>
                )}
                {isDeceased && (
                  <div className="text-[10px] mt-0.5" style={{ color: theme.nodeSubtext }}>{t('treeForm.deceasedLabel')}</div>
                )}
              </div>
            </div>
          </div>
        </div>
        <Handle type="source" position={Position.Bottom} className="!opacity-0 !pointer-events-none" />
      </>
    );
  }

  // ── Normal interactive mode ────────────────────────────────────────────────
  return (
    <>
      <Handle type="target" position={Position.Top} className="!opacity-0 !pointer-events-none" />

      {/* Outer wrapper — overflow visible so the details panel can float below */}
      <div style={{ width: PERSON_NODE_WIDTH, position: 'relative' }}>

        {/* Expand parents button */}
        {hasHiddenParents && (
          <ExpandButton direction="up" isExpanded={isExpanded} onClick={handleExpandUp} />
        )}

        {/* Card */}
        <div
          onClick={handleClick}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          title={fullName}
          style={{
            width: PERSON_NODE_WIDTH,
            height: PERSON_NODE_HEIGHT,
            position: 'relative',
            cursor: dragging ? 'grabbing' : 'grab',
            transform: dragging ? 'scale(1.06)' : 'scale(1)',
            transition: dragging
              ? 'box-shadow 0.1s ease, transform 0.1s ease'
              : 'transform 0.45s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.25s ease',
            zIndex: dragging ? 999 : undefined,
          }}
        >
          <div
            className="w-full h-full rounded-xl flex items-center gap-3 px-3 transition-all"
            style={{
              background: cardBg,
              border: `2px solid ${selected ? borderColor : isFocus ? borderColor : theme.nodeBorder}`,
              boxShadow: dragging
                ? `0 16px 40px rgba(0,0,0,0.22), 0 0 0 2px ${borderColor}66`
                : selected
                ? `0 0 0 3px ${borderColor}33, 0 4px 12px ${borderColor}22`
                : isFocus
                ? `0 0 0 2px ${borderColor}44`
                : '0 1px 3px rgba(0,0,0,0.08)',
            }}
          >
            {/* Left accent bar */}
            <div className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r" style={{ background: borderColor }} />

            <Avatar photoUrl={photoUrl} givenName={displayGivenName} surname={displaySurname} sex={sex} />

            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm leading-tight truncate" style={{ color: theme.nodeText }}>
                {fullName}
              </div>
              {years && (
                <div className="text-xs mt-0.5" style={{ color: theme.nodeSubtext }}>{years}</div>
              )}
              {isFocus && (
                <div
                  className="inline-flex items-center text-[10px] font-medium px-1.5 py-0.5 rounded mt-1"
                  style={{ background: `${borderColor}20`, color: borderColor }}
                >
                  Focus
                </div>
              )}
              {isDeceased && !isFocus && (
                <div className="text-[10px] mt-0.5" style={{ color: theme.nodeSubtext }}>{t('treeForm.deceasedLabel')}</div>
              )}
            </div>

            {/* Details toggle — always visible if there is detail data, otherwise subtle */}
            <button
              onClick={handleDetailsToggle}
              onMouseDown={(e) => e.stopPropagation()}
              className="flex-shrink-0 flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-1 rounded-md transition-colors"
              style={{
                color: detailsOpen ? borderColor : theme.nodeSubtext,
                background: detailsOpen ? `${borderColor}15` : 'transparent',
                opacity: hasDetails ? 1 : 0.4,
              }}
              title={detailsOpen ? 'Hide details' : 'Show details'}
            >
              {detailsOpen ? '▲' : '▼'}
            </button>
          </div>
        </div>

        {/* Details panel — floats below card, doesn't affect layout */}
        {detailsOpen && (
          <div
            style={{
              position: 'absolute',
              top: PERSON_NODE_HEIGHT - 2,
              left: 0,
              width: PERSON_NODE_WIDTH,
              zIndex: 1000,
              filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.14))',
            }}
            onMouseDown={(e) => e.stopPropagation()}
          >
            <DetailsPanel
              data={data}
              borderColor={borderColor}
              bg={cardBg}
              textColor={theme.nodeText}
              subtextColor={theme.nodeSubtext}
              borderCss={selected ? borderColor : isFocus ? borderColor : theme.nodeBorder}
            />
          </div>
        )}

        {/* Expand children button */}
        {hasHiddenChildren && (
          <ExpandButton direction="down" isExpanded={isExpanded} onClick={handleExpandDown} />
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!opacity-0 !pointer-events-none" />
    </>
  );
}

export const PersonNode = memo(PersonNodeComponent);
PersonNode.displayName = 'PersonNode';
export default PersonNode;
