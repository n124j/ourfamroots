/**
 * TimelineView — horizontal timeline showing people as bars across a year axis.
 *
 * Each person is a horizontal bar spanning birth year → death year (or present).
 * Years are shown on the X-axis. Color-coded by sex.
 * People with no birth date are listed in a separate section below the timeline.
 */

import React, { memo, useMemo, useRef, useState, useCallback, useEffect } from 'react';
import type { ApiTreeGraph, ApiPerson } from '../types';
import { useThemeStore } from '@store/theme.store';
import { useCanvasStore } from '@store/canvas.store';

const CURRENT_YEAR = new Date().getFullYear();
const ROW_HEIGHT = 28;
const ROW_GAP = 2;
const HEADER_HEIGHT = 50;
const MIN_PX_PER_YEAR = 4;
const MAX_PX_PER_YEAR = 30;
const LABEL_COL_W = 160;
const MIN_ROW_SLOT_H = 10; // minimum row height — allows up to ~60 members in a 700px container

const SEX_BAR_COLORS: Record<string, { bar: string; text: string }> = {
  MALE:    { bar: '#4a90b8', text: '#ffffff' },
  FEMALE:  { bar: '#b05070', text: '#ffffff' },
  OTHER:   { bar: '#8b5cf6', text: '#ffffff' },
  UNKNOWN: { bar: '#94a3b8', text: '#ffffff' },
};

const SEX_LABEL: Record<string, string> = {
  MALE: 'Male', FEMALE: 'Female', OTHER: 'Other', UNKNOWN: '',
};

interface TimelineViewProps {
  graph: ApiTreeGraph;
}

interface PersonWithBirth extends ApiPerson {
  birthYear: number;
  deathYear: number | undefined;
}

interface PersonNoBirth extends ApiPerson {
  birthYear: undefined;
  deathYear: number | undefined;
}

type EnrichedPerson = PersonWithBirth | PersonNoBirth;

interface HoveredInfo {
  person: EnrichedPerson;
  rect: DOMRect;
}

function parseYear(raw: unknown): number | undefined {
  if (raw == null) return undefined;
  const n = typeof raw === 'number' ? raw : parseInt(String(raw), 10);
  return !isNaN(n) && n > 100 ? n : undefined; // >100 AD filters out zeros/garbage
}

function resolveBirthYear(p: ApiPerson): number | undefined {
  // p.birthYear may arrive as number OR (runtime bug) as string — handle both
  const fromYear = parseYear((p as any).birthYear);
  if (fromYear !== undefined) return fromYear;
  if (p.birthDate) return parseYear(p.birthDate.slice(0, 4));
  return undefined;
}

function resolveDeathYear(p: ApiPerson): number | undefined {
  const fromYear = parseYear((p as any).deathYear);
  if (fromYear !== undefined) return fromYear;
  if (p.deathDate) return parseYear(p.deathDate.slice(0, 4));
  return undefined;
}

/** Tooltip card shown on hover over a person bar or no-date row */
function PersonTooltip({ info, theme }: { info: HoveredInfo; theme: any }) {
  const { person, rect } = info;
  const name = [person.displayGivenName, person.displaySurname].filter(Boolean).join(' ') || 'Unknown';
  const colors = SEX_BAR_COLORS[person.sex] ?? SEX_BAR_COLORS.UNKNOWN;

  const birthStr = person.birthYear ?? (person.birthDate ? person.birthDate.slice(0, 4) : null);
  const deathStr = person.deathYear ?? (person.deathDate ? person.deathDate.slice(0, 4) : null);
  const lifespan = birthStr
    ? `${birthStr} – ${deathStr ?? (person.isLiving ? 'present' : '?')}`
    : null;

  const bornPlace = [person.bornCity, person.bornCountry].filter(Boolean).join(', ');
  const diedPlace = [person.diedCity, person.diedCountry].filter(Boolean).join(', ');

  const TOOLTIP_H = 130;
  const spaceBelow = window.innerHeight - rect.bottom;
  const top = spaceBelow >= TOOLTIP_H + 8
    ? rect.bottom + 4
    : rect.top - TOOLTIP_H - 4;

  const TOOLTIP_W = 220;
  const left = Math.min(Math.max(rect.left, 8), window.innerWidth - TOOLTIP_W - 8);

  return (
    <div
      style={{
        position: 'fixed',
        top,
        left,
        width: TOOLTIP_W,
        zIndex: 9999,
        background: theme.nodeBg,
        border: `1px solid ${theme.nodeBorder}`,
        borderRadius: 10,
        boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
        padding: '10px 12px',
        pointerEvents: 'none',
        display: 'flex',
        gap: 10,
        alignItems: 'flex-start',
      }}
    >
      <div
        style={{
          width: 48,
          height: 48,
          borderRadius: 8,
          overflow: 'hidden',
          flexShrink: 0,
          background: colors.bar + '33',
          border: `2px solid ${colors.bar}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {person.photoUrl ? (
          <img
            src={person.photoUrl}
            alt={name}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <span style={{ fontSize: 22, lineHeight: 1 }}>
            {person.sex === 'MALE' ? '♂' : person.sex === 'FEMALE' ? '♀' : '?'}
          </span>
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontWeight: 700,
            fontSize: 13,
            color: theme.nodeText,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {name}
        </div>

        {lifespan ? (
          <div style={{ fontSize: 11, color: theme.nodeSubtext, marginTop: 2 }}>{lifespan}</div>
        ) : (
          <div style={{ fontSize: 11, color: theme.nodeSubtext, marginTop: 2, fontStyle: 'italic' }}>
            Birth year unknown
          </div>
        )}

        {person.isLiving && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 3 }}>
            <span style={{ display: 'inline-block', width: 7, height: 7, borderRadius: '50%', background: '#22c55e' }} />
            <span style={{ fontSize: 10, color: '#22c55e', fontWeight: 600 }}>Living</span>
          </div>
        )}

        {bornPlace && (
          <div style={{ fontSize: 10, color: theme.nodeSubtext, marginTop: 4 }}>b. {bornPlace}</div>
        )}
        {diedPlace && (
          <div style={{ fontSize: 10, color: theme.nodeSubtext, marginTop: 1 }}>d. {diedPlace}</div>
        )}

        {SEX_LABEL[person.sex] && (
          <div
            style={{
              marginTop: 5,
              display: 'inline-block',
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: '0.05em',
              textTransform: 'uppercase',
              color: colors.bar,
              background: colors.bar + '22',
              borderRadius: 4,
              padding: '1px 5px',
            }}
          >
            {SEX_LABEL[person.sex]}
          </div>
        )}
      </div>
    </div>
  );
}

function TimelineViewComponent({ graph }: TimelineViewProps) {
  const theme = useThemeStore((s) => s.theme);
  const setSelectedPersonId = useCanvasStore((s) => s.setSelectedPersonId);
  const selectedPersonId = useCanvasStore((s) => s.selectedPersonId);

  const containerRef   = useRef<HTMLDivElement>(null);
  const leftColRef     = useRef<HTMLDivElement>(null);
  const barAreaRef     = useRef<HTMLDivElement>(null);
  const isSyncing      = useRef(false);
  const isPanning      = useRef(false);
  const panOrigin      = useRef({ x: 0, y: 0 });
  const scrollOrigin   = useRef({ left: 0, top: 0 });
  const hasDragged     = useRef(false);
  const suppressClick  = useRef(false);
  // Use a ref (not state) for the fit-done flag so React Fast Refresh doesn't preserve a stale true
  const fittedRef      = useRef(false);
  const [panning, setPanning] = useState(false);
  const [pxPerYear, setPxPerYear] = useState(MIN_PX_PER_YEAR); // start at min — visible for any tree
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 }); // tracked by ResizeObserver
  const [scrollTop, setScrollTop] = useState(0);           // drives virtual-row windowing
  const [showLines, setShowLines] = useState(true);
  const [hoveredInfo, setHoveredInfo] = useState<HoveredInfo | null>(null);

  // People with a resolvable birth year — shown as bars on the year axis
  const sortedPeople = useMemo((): PersonWithBirth[] => {
    const enriched = graph.persons.map((p) => ({
      ...p,
      birthYear: resolveBirthYear(p),
      deathYear: resolveDeathYear(p),
    }));
    return (enriched.filter((p) => p.birthYear != null) as PersonWithBirth[])
      .sort((a, b) => a.birthYear - b.birthYear);
  }, [graph.persons]);

  // People without any resolvable birth year — shown in a section below
  const noBirthPeople = useMemo((): PersonNoBirth[] => {
    const withBirth = new Set(sortedPeople.map((p) => p.id));
    return graph.persons
      .filter((p) => !withBirth.has(p.id))
      .map((p) => ({ ...p, birthYear: undefined as undefined, deathYear: resolveDeathYear(p) }));
  }, [graph.persons, sortedPeople]);

  const { minYear, maxYear } = useMemo(() => {
    if (sortedPeople.length === 0) return { minYear: 1800, maxYear: CURRENT_YEAR };
    const births = sortedPeople.map((p) => p.birthYear as number);
    const deaths = sortedPeople.map(
      (p) => p.deathYear ?? (p.isLiving ? CURRENT_YEAR : (p.birthYear as number) + 80)
    );
    const min = Math.min(...births);
    const max = Math.max(...deaths, CURRENT_YEAR);
    return {
      minYear: Math.floor(min / 10) * 10 - 10,
      maxYear: Math.ceil(max / 10) * 10 + 10,
    };
  }, [sortedPeople]);

  const totalYears = maxYear - minYear;
  const totalWidth = totalYears * pxPerYear;

  // ── ResizeObserver: track real container dimensions ──────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Read initial size immediately
    setContainerSize({ w: el.clientWidth, h: el.clientHeight });
    const obs = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (r) setContainerSize({ w: r.width, h: r.height });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset fit flag whenever the tree data changes so the view re-fits on new data
  useEffect(() => {
    fittedRef.current = false;
  }, [graph.persons]);

  // Dynamic row slot height — purely computed, no timing issues
  const rowSlotH = useMemo(() => {
    const N = sortedPeople.length;
    if (containerSize.h === 0 || N === 0) return ROW_HEIGHT + ROW_GAP;
    const availH = containerSize.h - HEADER_HEIGHT - 20;
    if (availH <= 0) return ROW_HEIGHT + ROW_GAP;
    const dynSlot = Math.floor(availH / N);
    return Math.max(MIN_ROW_SLOT_H, Math.min(ROW_HEIGHT + ROW_GAP, dynSlot));
  }, [containerSize.h, sortedPeople.length]);

  // Height of the year-axis rows + the no-birth section (both use the dynamic rowSlotH)
  const NO_BIRTH_SECTION_HEADER = noBirthPeople.length > 0 ? 36 : 0;
  const NO_BIRTH_ROW_H = rowSlotH;
  const timelineHeight = HEADER_HEIGHT + sortedPeople.length * rowSlotH + 20;
  const totalHeight = timelineHeight + NO_BIRTH_SECTION_HEADER + noBirthPeople.length * NO_BIRTH_ROW_H + 40;

  // ── Virtual windowing ────────────────────────────────────────────────────────
  // Only render rows that are currently in (or near) the viewport.
  // This keeps DOM node count bounded even for 500+ member trees.
  const OVERSCAN = 8; // extra rows to render above and below the visible viewport
  const { visStart, visEnd } = useMemo(() => {
    const N = sortedPeople.length;
    if (N === 0 || rowSlotH === 0 || containerSize.h === 0) return { visStart: 0, visEnd: N };
    // Row idx occupies Y = HEADER_HEIGHT + idx * rowSlotH … + rowSlotH
    const firstVis = Math.floor((scrollTop - HEADER_HEIGHT) / rowSlotH);
    const lastVis  = Math.ceil((scrollTop + containerSize.h - HEADER_HEIGHT) / rowSlotH);
    return {
      visStart: Math.max(0, firstVis - OVERSCAN),
      visEnd:   Math.min(N, lastVis + OVERSCAN + 1),
    };
  }, [scrollTop, containerSize.h, rowSlotH, sortedPeople.length]);

  const yearToX = useCallback((year: number) => (year - minYear) * pxPerYear, [minYear, pxPerYear]);

  const handleZoomIn  = useCallback(() => setPxPerYear((v) => Math.min(v + 2, MAX_PX_PER_YEAR)), []);
  const handleZoomOut = useCallback(() => setPxPerYear((v) => Math.max(v - 2, MIN_PX_PER_YEAR)), []);

  // Fit horizontal zoom so all bars are in view without horizontal scrolling
  const fitToContainer = useCallback(() => {
    const { w } = containerSize;
    if (w === 0 || totalYears === 0) return;
    const barAreaW = w - LABEL_COL_W - 40;
    if (barAreaW <= 0) return;
    const fitPx = Math.floor(barAreaW / totalYears);
    setPxPerYear(Math.max(MIN_PX_PER_YEAR, Math.min(fitPx, MAX_PX_PER_YEAR)));
  }, [containerSize, totalYears]);

  // Auto-fit pxPerYear once per data load, as soon as the container has real dimensions.
  // Always start at the top (oldest members) so the user can scroll/pan downward to see more.
  useEffect(() => {
    if (fittedRef.current || containerSize.w === 0 || totalYears === 0) return;
    fitToContainer();
    fittedRef.current = true;
    // Reset both panels to the top so virtual window starts at row 0
    if (barAreaRef.current)  barAreaRef.current.scrollTop  = 0;
    if (leftColRef.current)  leftColRef.current.scrollTop  = 0;
    setScrollTop(0);
  }, [containerSize.w, totalYears, fitToContainer]);

  // Synchronized vertical scrolling between left name column and bar area
  const handleBarAreaScroll = useCallback(() => {
    setHoveredInfo(null);
    if (!barAreaRef.current) return;
    const st = barAreaRef.current.scrollTop;
    setScrollTop(st);                                  // drives virtual windowing
    if (isSyncing.current || !leftColRef.current) return;
    isSyncing.current = true;
    leftColRef.current.scrollTop = st;
    isSyncing.current = false;
  }, []);

  const handleLeftColScroll = useCallback(() => {
    if (isSyncing.current || !leftColRef.current || !barAreaRef.current) return;
    isSyncing.current = true;
    const st = leftColRef.current.scrollTop;
    barAreaRef.current.scrollTop = st;
    setScrollTop(st);                                  // drives virtual windowing
    isSyncing.current = false;
  }, []);

  // ── Drag-to-pan ────────────────────────────────────────────────────────────

  // handlePanMouseDown works for BOTH the bar area (full 2D pan) and the left column (vertical-only pan)
  const handlePanMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0 || !barAreaRef.current) return;
    isPanning.current = true;
    hasDragged.current = false;
    panOrigin.current = { x: e.clientX, y: e.clientY };
    scrollOrigin.current = {
      left: barAreaRef.current.scrollLeft,
      top:  barAreaRef.current.scrollTop,
    };
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isPanning.current || !barAreaRef.current) return;
      const dx = e.clientX - panOrigin.current.x;
      const dy = e.clientY - panOrigin.current.y;
      if (!hasDragged.current && (Math.abs(dx) > 4 || Math.abs(dy) > 4)) {
        hasDragged.current = true;
        setPanning(true);
        setHoveredInfo(null);
      }
      if (!hasDragged.current) return;
      barAreaRef.current.scrollLeft = scrollOrigin.current.left - dx;
      barAreaRef.current.scrollTop  = scrollOrigin.current.top  - dy;
      setScrollTop(barAreaRef.current.scrollTop); // drive virtual windowing during pan
      // keep left column in sync
      if (!isSyncing.current && leftColRef.current) {
        isSyncing.current = true;
        leftColRef.current.scrollTop = barAreaRef.current.scrollTop;
        isSyncing.current = false;
      }
    };
    const onUp = () => {
      if (hasDragged.current) suppressClick.current = true;
      isPanning.current  = false;
      hasDragged.current = false;
      setPanning(false);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const decadeInterval = pxPerYear < 8 ? 20 : 10;

  const decades = useMemo(() => {
    const result: number[] = [];
    const start = Math.ceil(minYear / decadeInterval) * decadeInterval;
    for (let y = start; y <= maxYear; y += decadeInterval) result.push(y);
    return result;
  }, [minYear, maxYear, decadeInterval]);

  const getName = (p: ApiPerson) =>
    [p.displayGivenName, p.displaySurname].filter(Boolean).join(' ') || 'Unknown';

  const getEndYear = (p: PersonWithBirth) => {
    if (p.deathYear) return p.deathYear;
    if (p.isLiving)  return CURRENT_YEAR;
    return p.birthYear + 75;
  };

  const totalPeople = graph.persons.length;

  if (sortedPeople.length === 0 && noBirthPeople.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2" style={{ color: theme.nodeSubtext }}>
        <span className="text-lg">No people in this tree</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full" style={{ background: theme.canvasBg }}>
      {/* Controls bar */}
      <div
        className="flex items-center gap-2 px-4 py-2 border-b"
        style={{ background: theme.nodeBg, borderColor: theme.nodeBorder }}
      >
        <span className="text-sm font-semibold" style={{ color: theme.nodeText }}>Timeline</span>
        <div className="flex-1" />
        <button
          onClick={() => setShowLines((v) => !v)}
          title="Show or hide the decade/century vertical gridlines"
          className="px-2.5 py-1 text-xs rounded border transition-colors"
          style={{
            background: showLines ? theme.edgeHighlight : theme.nodeBg,
            color: showLines ? '#fff' : theme.nodeText,
            borderColor: theme.nodeBorder,
          }}
        >
          Toggle Lines
        </button>
        <button
          onClick={handleZoomOut}
          className="px-2 py-1 text-xs rounded border"
          style={{ background: theme.nodeBg, color: theme.nodeText, borderColor: theme.nodeBorder }}
        >
          &minus;
        </button>
        <span className="text-xs min-w-[40px] text-center" style={{ color: theme.nodeSubtext }}>
          {pxPerYear}px/yr
        </span>
        <button
          onClick={handleZoomIn}
          className="px-2 py-1 text-xs rounded border"
          style={{ background: theme.nodeBg, color: theme.nodeText, borderColor: theme.nodeBorder }}
        >
          +
        </button>
      </div>

      {/* Scrollable timeline — two-panel layout: fixed name column + scrollable bar area */}
      <div
        ref={containerRef}
        className="flex-1 flex overflow-hidden min-h-0"
      >
        {/* Fixed left column: person names — also pannable vertically */}
        <div
          ref={leftColRef}
          onScroll={handleLeftColScroll}
          onMouseDown={handlePanMouseDown}
          onClickCapture={(e) => {
            if (suppressClick.current) {
              e.stopPropagation();
              suppressClick.current = false;
            }
          }}
          className="scrollbar-none"
          style={{
            width: LABEL_COL_W,
            flexShrink: 0,
            borderRight: `1px solid ${theme.nodeBorder}`,
            overflowY: 'scroll',
            overflowX: 'hidden',
            cursor: panning ? 'grabbing' : 'grab',
          }}
        >
          {/* Sticky header spacer — stays at top while scrolling down */}
          <div style={{
            position: 'sticky',
            top: 0,
            height: HEADER_HEIGHT,
            background: theme.nodeBg,
            borderBottom: `1px solid ${theme.nodeBorder}`,
            zIndex: 5,
            flexShrink: 0,
          }} />

          {/* Virtual windowing: top spacer preserves scroll range without rendering off-screen rows */}
          {visStart > 0 && <div style={{ height: visStart * rowSlotH }} />}

          {/* Only render label rows in the visible window [visStart, visEnd) */}
          {sortedPeople.slice(visStart, visEnd).map((person, i) => {
            const colors = SEX_BAR_COLORS[person.sex] ?? SEX_BAR_COLORS.UNKNOWN;
            const name = getName(person);
            const isSelected = selectedPersonId === person.id;
            const isHovered = hoveredInfo?.person.id === person.id;
            void i; // idx = visStart + i (position already encoded by spacers)
            return (
              <div
                key={`lbl-${person.id}`}
                onClick={() => setSelectedPersonId(person.id)}
                onMouseEnter={(e) => setHoveredInfo({ person, rect: e.currentTarget.getBoundingClientRect() })}
                onMouseLeave={() => setHoveredInfo(null)}
                style={{
                  height: rowSlotH,
                  display: 'flex',
                  alignItems: 'center',
                  paddingLeft: 8,
                  paddingRight: 6,
                  gap: 5,
                  cursor: 'pointer',
                  background: isSelected
                    ? colors.bar + '22'
                    : isHovered
                    ? colors.bar + '14'
                    : 'transparent',
                  borderBottom: `1px solid ${theme.canvasDot}`,
                }}
              >
                <div
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    background: colors.bar,
                    flexShrink: 0,
                  }}
                />
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: isSelected ? 700 : 500,
                    color: theme.nodeText,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  {name}
                </span>
                <span style={{ fontSize: 9, color: theme.nodeSubtext, flexShrink: 0 }}>
                  {person.birthYear}
                </span>
              </div>
            );
          })}

          {/* Bottom spacer — preserves total scroll height identical to rendering all rows */}
          {visEnd < sortedPeople.length && (
            <div style={{ height: (sortedPeople.length - visEnd) * rowSlotH }} />
          )}

          {/* No-birth section label rows */}
          {noBirthPeople.length > 0 && (
            <>
              <div
                style={{
                  height: NO_BIRTH_SECTION_HEADER,
                  display: 'flex',
                  alignItems: 'center',
                  paddingLeft: 8,
                  gap: 6,
                  borderTop: `1px dashed ${theme.nodeBorder}`,
                }}
              >
                <span style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: theme.nodeSubtext }}>
                  No birth year
                </span>
                <span style={{ fontSize: 9, color: theme.nodeSubtext, opacity: 0.65 }}>
                  ({noBirthPeople.length} — edit person to add a birth year)
                </span>
              </div>
              {noBirthPeople.map((person) => {
                const colors = SEX_BAR_COLORS[person.sex] ?? SEX_BAR_COLORS.UNKNOWN;
                const name = getName(person);
                const isSelected = selectedPersonId === person.id;
                const isHovered = hoveredInfo?.person.id === person.id;
                return (
                  <div
                    key={`lbl-nb-${person.id}`}
                    onClick={() => setSelectedPersonId(person.id)}
                    onMouseEnter={(e) => setHoveredInfo({ person: person as EnrichedPerson, rect: e.currentTarget.getBoundingClientRect() })}
                    onMouseLeave={() => setHoveredInfo(null)}
                    style={{
                      height: rowSlotH,
                      display: 'flex',
                      alignItems: 'center',
                      paddingLeft: 8,
                      paddingRight: 6,
                      gap: 5,
                      cursor: 'pointer',
                      background: isSelected
                        ? colors.bar + '22'
                        : isHovered
                        ? colors.bar + '14'
                        : 'transparent',
                      borderBottom: `1px solid ${theme.canvasDot}`,
                    }}
                  >
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: colors.bar, flexShrink: 0 }} />
                    <span style={{ fontSize: 10, color: theme.nodeText, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {name}
                    </span>
                  </div>
                );
              })}
            </>
          )}
        </div>

        {/* Scrollable bar area — drag to pan */}
        <div
          ref={barAreaRef}
          className="flex-1"
          onScroll={handleBarAreaScroll}
          onMouseDown={handlePanMouseDown}
          onClickCapture={(e) => {
            if (suppressClick.current) {
              e.stopPropagation();
              suppressClick.current = false;
            }
          }}
          style={{ overflowY: 'scroll', overflowX: 'auto', cursor: panning ? 'grabbing' : 'grab' }}
        >
        <div style={{ width: Math.max(totalWidth + 40, 400), minHeight: totalHeight, position: 'relative', padding: '0 20px' }}>

          {/* ── Sticky year header — stays pinned at top while scrolling down ── */}
          {sortedPeople.length > 0 && (
            <div style={{
              position: 'sticky',
              top: 0,
              zIndex: 5,
              height: HEADER_HEIGHT,
              margin: '0 -20px',       // extend past the content padding to full div width
              background: theme.nodeBg,
              borderBottom: `1px solid ${theme.nodeBorder}`,
            }}>
              {decades.map((year) => {
                const x = yearToX(year);
                const isCentury = year % 100 === 0;
                return (
                  <div
                    key={`dl-${year}`}
                    style={{
                      position: 'absolute',
                      left: x + 20,
                      top: 0,
                      transform: 'translateX(-50%)',
                      fontSize: isCentury ? 13 : 10,
                      fontWeight: isCentury ? 700 : 400,
                      color: isCentury ? theme.nodeText : theme.nodeSubtext,
                      height: HEADER_HEIGHT,
                      display: 'flex',
                      alignItems: 'center',
                      userSelect: 'none',
                    }}
                  >
                    {year}
                  </div>
                );
              })}
            </div>
          )}

          {/* Decade gridlines (drawn behind bars, below the sticky header) */}
          {showLines && sortedPeople.length > 0 && decades.map((year) => {
            const x = yearToX(year);
            const isCentury = year % 100 === 0;
            return (
              <div
                key={`dg-${year}`}
                style={{
                  position: 'absolute',
                  left: x + 20,
                  top: HEADER_HEIGHT,
                  width: 1,
                  height: timelineHeight - HEADER_HEIGHT,
                  background: isCentury ? theme.nodeBorder : theme.canvasDot,
                  zIndex: 0,
                }}
              />
            );
          })}

          {/* Person bars — only render visible window [visStart, visEnd) */}
          {sortedPeople.slice(visStart, visEnd).map((person, i) => {
            const idx = visStart + i;
            const startX = yearToX(person.birthYear);
            const endX   = yearToX(getEndYear(person));
            const barWidth = Math.max(endX - startX, 3);
            const barH = Math.max(14, rowSlotH - 4);
            const y = HEADER_HEIGHT + idx * rowSlotH + Math.floor((rowSlotH - barH) / 2);
            const colors = SEX_BAR_COLORS[person.sex] ?? SEX_BAR_COLORS.UNKNOWN;
            const isSelected = selectedPersonId === person.id;
            const isHovered  = hoveredInfo?.person.id === person.id;
            const name  = getName(person);
            const label = `${name} (${person.birthYear}–${person.deathYear ?? 'living'})`;

            return (
              <div
                key={person.id}
                onClick={() => setSelectedPersonId(person.id)}
                onMouseEnter={(e) => setHoveredInfo({ person, rect: e.currentTarget.getBoundingClientRect() })}
                onMouseLeave={() => setHoveredInfo(null)}
                style={{
                  position: 'absolute',
                  left: startX + 20,
                  top: y,
                  width: barWidth,
                  height: barH,
                  background: person.isLiving
                    ? `linear-gradient(90deg, ${colors.bar}, ${colors.bar}cc)`
                    : colors.bar,
                  borderRadius: 4,
                  cursor: 'pointer',
                  border: isSelected
                    ? '2px solid #f97316'
                    : isHovered
                    ? `2px solid ${colors.bar}`
                    : '1px solid transparent',
                  boxShadow: isSelected
                    ? '0 0 0 2px #f9741644'
                    : isHovered
                    ? `0 2px 8px ${colors.bar}55`
                    : undefined,
                  display: 'flex',
                  alignItems: 'center',
                  paddingLeft: 6,
                  paddingRight: 6,
                  overflow: 'hidden',
                  zIndex: isHovered ? 4 : 1,
                  transition: 'border 0.1s, box-shadow 0.1s',
                  opacity: isHovered ? 1 : 0.92,
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 500,
                    color: colors.text,
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    textShadow: '0 1px 2px rgba(0,0,0,0.3)',
                  }}
                >
                  {barWidth > 60 ? label : barWidth > 30 ? name : ''}
                </span>
              </div>
            );
          })}

          {/* Birth year dot markers — same visible window */}
          {sortedPeople.slice(visStart, visEnd).map((person, i) => {
            const idx = visStart + i;
            const startX = yearToX(person.birthYear);
            const y = HEADER_HEIGHT + idx * rowSlotH;
            return (
              <div
                key={`marker-${person.id}`}
                style={{
                  position: 'absolute',
                  left: startX + 20 - 2,
                  top: y - 2,
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: SEX_BAR_COLORS[person.sex]?.bar ?? '#94a3b8',
                  border: `1.5px solid ${theme.nodeBg}`,
                  zIndex: 3,
                }}
              />
            );
          })}

          {/* ── No birth date section — just spacer rows (names shown in left column) */}
          {noBirthPeople.length > 0 && (
            <>
              {/* Section divider line */}
              <div
                style={{
                  position: 'absolute',
                  left: 0,
                  top: timelineHeight,
                  width: '100%',
                  height: NO_BIRTH_SECTION_HEADER,
                  borderTop: `1px dashed ${theme.nodeBorder}`,
                  zIndex: 2,
                }}
              />
              {/* Alternating row backgrounds so rows align with left column */}
              {noBirthPeople.map((_, idx) => {
                const y = timelineHeight + NO_BIRTH_SECTION_HEADER + idx * NO_BIRTH_ROW_H;
                return (
                  <div
                    key={`nb-stripe-${idx}`}
                    style={{
                      position: 'absolute',
                      left: 0,
                      top: y,
                      width: '100%',
                      height: NO_BIRTH_ROW_H,
                      background: idx % 2 === 0 ? theme.canvasDot + '18' : 'transparent',
                    }}
                  />
                );
              })}
            </>
          )}
        </div>
        </div>
      </div>

      {/* Bottom status bar — live visible range */}
      {sortedPeople.length > 0 && (() => {
        // Compute which person rows are actually inside the current viewport
        const vpFirst = Math.max(1, Math.floor((scrollTop - HEADER_HEIGHT) / rowSlotH) + 1);
        const vpLast  = Math.min(sortedPeople.length,
                          Math.ceil((scrollTop + containerSize.h - HEADER_HEIGHT) / rowSlotH));
        const vpCount = Math.max(0, vpLast - vpFirst + 1);
        return (
          <div
            className="flex items-center gap-3 px-4 py-1.5 border-t text-xs shrink-0"
            style={{ background: theme.nodeBg, borderColor: theme.nodeBorder, color: theme.nodeSubtext }}
          >
            <span>
              <span style={{ color: theme.nodeText, fontWeight: 600 }}>{vpCount}</span>
              {' '}of{' '}
              <span style={{ color: theme.nodeText, fontWeight: 600 }}>{sortedPeople.length}</span>
              {' '}members visible
            </span>
            <span className="opacity-40">·</span>
            <span>rows {vpFirst}–{vpLast}</span>
            <span className="opacity-40">·</span>
            <span>{minYear}–{maxYear}</span>
            {noBirthPeople.length > 0 && (
              <>
                <span className="opacity-40">·</span>
                <span
                  className="opacity-60"
                  title="Edit these members to add a birth year so they appear as timeline bars"
                >
                  {noBirthPeople.length} without birth year
                </span>
              </>
            )}
            <span className="flex-1" />
            <span className="opacity-50 italic">drag to pan · scroll to zoom</span>
          </div>
        );
      })()}

      {/* Hover tooltip — fixed so it escapes the scrollable container */}
      {hoveredInfo && <PersonTooltip info={hoveredInfo} theme={theme} />}
    </div>
  );
}

export const TimelineView = memo(TimelineViewComponent);
TimelineView.displayName = 'TimelineView';
