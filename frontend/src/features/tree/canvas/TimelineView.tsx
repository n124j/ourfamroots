/**
 * TimelineView — horizontal timeline showing people as bars across a year axis.
 *
 * Each person is a horizontal bar spanning birth year → death year (or present).
 * Years are shown on the X-axis. Color-coded by sex.
 */

import React, { memo, useMemo, useRef, useState, useCallback } from 'react';
import type { ApiTreeGraph, ApiPerson } from '../types';
import { useThemeStore } from '@store/theme.store';
import { useCanvasStore } from '@store/canvas.store';

const CURRENT_YEAR = new Date().getFullYear();
const ROW_HEIGHT = 28;
const ROW_GAP = 2;
const HEADER_HEIGHT = 50;
const YEAR_LABEL_WIDTH = 40;
const MIN_PX_PER_YEAR = 4;
const MAX_PX_PER_YEAR = 30;

const SEX_BAR_COLORS: Record<string, { bar: string; text: string }> = {
  MALE:    { bar: '#4a90b8', text: '#ffffff' },
  FEMALE:  { bar: '#b05070', text: '#ffffff' },
  OTHER:   { bar: '#8b5cf6', text: '#ffffff' },
  UNKNOWN: { bar: '#94a3b8', text: '#ffffff' },
};

interface TimelineViewProps {
  graph: ApiTreeGraph;
}

function TimelineViewComponent({ graph }: TimelineViewProps) {
  const theme = useThemeStore((s) => s.theme);
  const setSelectedPersonId = useCanvasStore((s) => s.setSelectedPersonId);
  const selectedPersonId = useCanvasStore((s) => s.selectedPersonId);

  const containerRef = useRef<HTMLDivElement>(null);
  const [pxPerYear, setPxPerYear] = useState(10);
  const [showLines, setShowLines] = useState(true);

  const sortedPeople = useMemo(() => {
    return [...graph.persons]
      .filter((p) => p.birthYear != null)
      .sort((a, b) => (a.birthYear ?? 0) - (b.birthYear ?? 0));
  }, [graph.persons]);

  const { minYear, maxYear } = useMemo(() => {
    if (sortedPeople.length === 0) return { minYear: 1800, maxYear: CURRENT_YEAR };
    const births = sortedPeople.map((p) => p.birthYear!);
    const deaths = sortedPeople
      .map((p) => p.deathYear ?? (p.isLiving ? CURRENT_YEAR : (p.birthYear ?? 1800) + 80))
      .filter(Boolean);
    const min = Math.min(...births);
    const max = Math.max(...deaths, CURRENT_YEAR);
    return {
      minYear: Math.floor(min / 10) * 10 - 10,
      maxYear: Math.ceil(max / 10) * 10 + 10,
    };
  }, [sortedPeople]);

  const totalYears = maxYear - minYear;
  const totalWidth = totalYears * pxPerYear;
  const totalHeight = HEADER_HEIGHT + sortedPeople.length * (ROW_HEIGHT + ROW_GAP) + 40;

  const yearToX = useCallback((year: number) => {
    return (year - minYear) * pxPerYear;
  }, [minYear, pxPerYear]);

  const handleZoomIn = useCallback(() => {
    setPxPerYear((v) => Math.min(v + 2, MAX_PX_PER_YEAR));
  }, []);

  const handleZoomOut = useCallback(() => {
    setPxPerYear((v) => Math.max(v - 2, MIN_PX_PER_YEAR));
  }, []);

  const decadeInterval = pxPerYear < 8 ? 20 : 10;

  const decades = useMemo(() => {
    const result: number[] = [];
    const start = Math.ceil(minYear / decadeInterval) * decadeInterval;
    for (let y = start; y <= maxYear; y += decadeInterval) {
      result.push(y);
    }
    return result;
  }, [minYear, maxYear, decadeInterval]);

  const centuryYears = useMemo(() => {
    const result: number[] = [];
    const start = Math.ceil(minYear / 100) * 100;
    for (let y = start; y <= maxYear; y += 100) {
      result.push(y);
    }
    return result;
  }, [minYear, maxYear]);

  const getName = (p: ApiPerson) => {
    const parts = [p.displayGivenName, p.displaySurname].filter(Boolean);
    return parts.join(' ') || 'Unknown';
  };

  const getEndYear = (p: ApiPerson) => {
    if (p.deathYear) return p.deathYear;
    if (p.isLiving) return CURRENT_YEAR;
    return (p.birthYear ?? 1800) + 75;
  };

  if (sortedPeople.length === 0) {
    return (
      <div className="flex items-center justify-center h-full" style={{ color: theme.nodeSubtext }}>
        No people with birth years to display on the timeline.
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
        <span className="text-xs" style={{ color: theme.nodeSubtext }}>
          {sortedPeople.length} people &middot; {minYear}&ndash;{maxYear}
        </span>
        <div className="flex-1" />
        <button
          onClick={() => setShowLines((v) => !v)}
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

      {/* Scrollable timeline */}
      <div ref={containerRef} className="flex-1 overflow-auto">
        <div style={{ width: totalWidth + 80, minHeight: totalHeight, position: 'relative', padding: '0 40px' }}>

          {/* Decade gridlines + labels */}
          {decades.map((year) => {
            const x = yearToX(year);
            const isCentury = year % 100 === 0;
            return (
              <React.Fragment key={`d-${year}`}>
                {showLines && (
                  <div
                    style={{
                      position: 'absolute',
                      left: x + 40,
                      top: HEADER_HEIGHT,
                      width: 1,
                      height: totalHeight - HEADER_HEIGHT,
                      background: isCentury ? theme.nodeBorder : `${theme.canvasDot}`,
                      zIndex: 0,
                    }}
                  />
                )}
                <div
                  style={{
                    position: 'absolute',
                    left: x + 40,
                    top: 0,
                    transform: 'translateX(-50%)',
                    fontSize: isCentury ? 13 : 10,
                    fontWeight: isCentury ? 700 : 400,
                    color: isCentury ? theme.nodeText : theme.nodeSubtext,
                    height: HEADER_HEIGHT,
                    display: 'flex',
                    alignItems: 'center',
                    zIndex: 2,
                    userSelect: 'none',
                  }}
                >
                  {year}
                </div>
              </React.Fragment>
            );
          })}

          {/* Header separator line */}
          <div
            style={{
              position: 'absolute',
              left: 0,
              top: HEADER_HEIGHT - 1,
              width: '100%',
              height: 1,
              background: theme.nodeBorder,
              zIndex: 1,
            }}
          />

          {/* Person bars */}
          {sortedPeople.map((person, idx) => {
            const startX = yearToX(person.birthYear!);
            const endX = yearToX(getEndYear(person));
            const barWidth = Math.max(endX - startX, 3);
            const y = HEADER_HEIGHT + idx * (ROW_HEIGHT + ROW_GAP);
            const colors = SEX_BAR_COLORS[person.sex] ?? SEX_BAR_COLORS.UNKNOWN;
            const isSelected = selectedPersonId === person.id;
            const name = getName(person);
            const label = `${name} (${person.birthYear}–${person.deathYear ?? 'living'})`;

            return (
              <div
                key={person.id}
                onClick={() => setSelectedPersonId(person.id)}
                title={label}
                style={{
                  position: 'absolute',
                  left: startX + 40,
                  top: y,
                  width: barWidth,
                  height: ROW_HEIGHT,
                  background: person.isLiving
                    ? `linear-gradient(90deg, ${colors.bar}, ${colors.bar}cc)`
                    : colors.bar,
                  borderRadius: 4,
                  cursor: 'pointer',
                  border: isSelected ? '2px solid #f97316' : '1px solid transparent',
                  boxShadow: isSelected ? '0 0 0 2px #f9741644' : undefined,
                  display: 'flex',
                  alignItems: 'center',
                  paddingLeft: 6,
                  paddingRight: 6,
                  overflow: 'hidden',
                  zIndex: 1,
                  transition: 'border 0.15s',
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

          {/* Birth year markers on bars */}
          {sortedPeople.map((person, idx) => {
            const startX = yearToX(person.birthYear!);
            const y = HEADER_HEIGHT + idx * (ROW_HEIGHT + ROW_GAP);
            return (
              <div
                key={`marker-${person.id}`}
                style={{
                  position: 'absolute',
                  left: startX + 40 - 2,
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
        </div>
      </div>
    </div>
  );
}

export const TimelineView = memo(TimelineViewComponent);
TimelineView.displayName = 'TimelineView';
