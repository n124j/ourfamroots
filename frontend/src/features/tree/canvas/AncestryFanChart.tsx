/**
 * AncestryFanChart — SVG sunburst/wedge ancestor fan chart.
 *
 * Renders a semicircular fan with the focus person at the bottom centre.
 * Each generation forms a concentric ring split into equal wedge segments.
 * Four colour families (one per grandparent line) shade the chart.
 *
 * If focusPersonId is null/empty we automatically pick the first person
 * who has at least one ancestor in the graph.
 */

import React, { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ApiTreeGraph } from '../types';

// ── Constants ────────────────────────────────────────────────────────────────

const FOCUS_R = 80;   // radius of the centre circle
const RING_W  = 90;   // radial width of each generation ring (compact for 8 rings)

// 4 colour families × 8 shades (darker inner rings → lighter outer rings)
const PALETTE: readonly (readonly string[])[] = [
  ['#4aada3','#5db8ae','#72c2bb','#88ccc7','#9ed6d3','#b0ddd9','#c3e7e4','#d6f0ee'], // teal
  ['#5db87d','#70c48d','#83cf9e','#9bd4ae','#aedcc0','#bde2cb','#cce9d7','#dbf0e3'], // sage
  ['#b09c46','#b8a756','#c4b260','#cfbe6e','#d5c67d','#ddcf8e','#e4d8a2','#eee4bc'], // gold
  ['#d07060','#d47e6e','#da8a7a','#e09789','#e4a496','#e9b0a4','#f0c2b8','#f5d2cc'], // salmon
];

// ── Geometry helpers ─────────────────────────────────────────────────────────

/** Polar → SVG cartesian. deg: 0=right, 90=up (math convention). */
function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const rad = (deg * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy - r * Math.sin(rad)];
}

const f = (n: number) => n.toFixed(2);

/**
 * SVG path for an annular wedge.
 * a1, a2 ∈ [0°,180°], a1 < a2 (math convention: 0=right,90=top,180=left).
 */
function wedgePath(
  cx: number, cy: number,
  rIn: number, rOut: number,
  a1: number, a2: number,
): string {
  const [ix1, iy1] = polar(cx, cy, rIn,  a1);
  const [ix2, iy2] = polar(cx, cy, rIn,  a2);
  const [ox2, oy2] = polar(cx, cy, rOut, a2);
  const [ox1, oy1] = polar(cx, cy, rOut, a1);
  const la = (a2 - a1) >= 180 ? 1 : 0;
  return (
    `M${f(ix1)},${f(iy1)} ` +
    `A${f(rIn)},${f(rIn)} 0 ${la},0 ${f(ix2)},${f(iy2)} ` +
    `L${f(ox2)},${f(oy2)} ` +
    `A${f(rOut)},${f(rOut)} 0 ${la},1 ${f(ox1)},${f(oy1)} Z`
  );
}

// ── Tooltip helpers ───────────────────────────────────────────────────────────

function genLabel(gen: number): string {
  if (gen === 1) return 'Parent';
  if (gen === 2) return 'Grandparent';
  if (gen === 3) return 'Great-grandparent';
  return `${gen - 2}× Great-grandparent`;
}

// ── Data types ───────────────────────────────────────────────────────────────

interface WedgeInfo {
  personId: string;
  gen:  number;
  a1:   number;
  a2:   number;
  rIn:  number;
  rOut: number;
  color: string;
}

interface TooltipState {
  clientX: number;
  clientY: number;
  personId: string;
  gen: number;
}

// ── Component ────────────────────────────────────────────────────────────────

interface Props {
  graph:          ApiTreeGraph;
  focusPersonId:  string;
  maxGenerations?: number;
}

export function AncestryFanChart({ graph, focusPersonId, maxGenerations = 8 }: Props) {
  // ── Tooltip state ────────────────────────────────────────────────────────
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  // ── Resolve the effective focus person ──────────────────────────────────
  const effectiveFocusId = useMemo(() => {
    const personSet = new Set(graph.persons.map((p) => p.id));
    if (focusPersonId && personSet.has(focusPersonId)) return focusPersonId;

    const childIds = new Set<string>();
    for (const fg of graph.familyGroups) {
      for (const cId of Object.keys(fg.children)) {
        if (personSet.has(cId)) childIds.add(cId);
      }
    }

    const candidate = graph.persons.find((p) => childIds.has(p.id));
    return candidate?.id ?? graph.persons[0]?.id ?? '';
  }, [graph, focusPersonId]);

  // ── Build ancestor BFS ───────────────────────────────────────────────────

  const personMap = useMemo(
    () => new Map(graph.persons.map((p) => [p.id, p])),
    [graph.persons],
  );

  const { wedges, focusPerson } = useMemo(() => {
    const fgById = new Map(graph.familyGroups.map((fg) => [fg.id, fg]));

    const childToFG = new Map<string, string>();
    for (const fg of graph.familyGroups) {
      for (const cId of Object.keys(fg.children)) {
        childToFG.set(cId, fg.id);
      }
    }

    const bin = new Map<string, { gen: number; slot: number }>();
    if (effectiveFocusId) {
      bin.set(effectiveFocusId, { gen: 0, slot: 0 });
      const queue = [effectiveFocusId];

      while (queue.length > 0) {
        const pid = queue.shift()!;
        const { gen, slot } = bin.get(pid)!;
        if (gen >= maxGenerations) continue;

        const fgId = childToFG.get(pid);
        if (!fgId) continue;
        const fg = fgById.get(fgId);
        if (!fg) continue;

        fg.parentIds.forEach((pId, i) => {
          if (!bin.has(pId)) {
            bin.set(pId, { gen: gen + 1, slot: slot * 2 + i });
            queue.push(pId);
          }
        });
      }
    }

    const wedges: WedgeInfo[] = [];
    for (const [personId, { gen, slot }] of bin) {
      if (gen === 0) continue;

      const count = Math.pow(2, gen);
      const fanA1 = (slot       / count) * 180;
      const fanA2 = ((slot + 1) / count) * 180;
      const a1 = 180 - fanA2;
      const a2 = 180 - fanA1;

      const rIn  = FOCUS_R + (gen - 1) * RING_W;
      const rOut = FOCUS_R +  gen      * RING_W;

      const colorIdx = Math.min(3, Math.floor((slot / count) * 4));
      const shade    = Math.min(gen - 1, PALETTE[0].length - 1);
      const color    = PALETTE[colorIdx][shade];

      wedges.push({ personId, gen, a1, a2, rIn, rOut, color });
    }

    return { wedges, focusPerson: personMap.get(effectiveFocusId) };
  }, [graph, effectiveFocusId, maxGenerations, personMap]);

  // ── SVG viewport ────────────────────────────────────────────────────────
  const maxR  = FOCUS_R + maxGenerations * RING_W;
  const viewW = maxR * 2 + 40;
  const viewH = maxR + FOCUS_R + 40;
  const CX    = viewW / 2;
  const CY    = maxR + 20;

  const focusYears = [
    focusPerson?.birthYear,
    focusPerson?.isLiving ? 'Living' : focusPerson?.deathYear,
  ].filter(Boolean).join('–');

  const hasAncestors = wedges.length > 0;

  // ── Tooltip person data ──────────────────────────────────────────────────
  const tooltipPerson = tooltip ? personMap.get(tooltip.personId) : null;
  const tooltipYears  = tooltipPerson
    ? [
        tooltipPerson.birthYear,
        tooltipPerson.isLiving ? 'Living' : tooltipPerson.deathYear,
      ].filter(Boolean).join('–')
    : '';

  return (
    <>
      <div style={{ lineHeight: 0 }}>
        <svg
          viewBox={`0 0 ${viewW} ${viewH}`}
          width={viewW}
          height={viewH}
          style={{ display: 'block' }}
          aria-label="Ancestry fan chart"
          onMouseLeave={() => setTooltip(null)}
        >
          {/* ── Hover highlight style ── */}
          <style>{`
            .fan-wedge { cursor: pointer; transition: filter 0.1s; }
            .fan-wedge:hover { filter: brightness(0.82); }
            .fan-focus { cursor: default; }
          `}</style>

          {/* ── Wedges ── */}
          {wedges.map(({ personId, gen, a1, a2, rIn, rOut, color }) => {
            const person = personMap.get(personId);
            const span   = a2 - a1;
            if (span < 1) return null;

            const tA = (a1 + a2) / 2;
            const tR = (rIn + rOut) / 2;
            const [tx, ty] = polar(CX, CY, tR, tA);

            // < 10° → radial text (runs outward along radius)
            // ≥ 10° → tangential text (follows the arc)
            const useRadial = span < 10;
            const rotation  = useRadial ? -tA : (90 - tA);

            const surname   = (person?.displaySurname  ?? '').toUpperCase();
            const givenName =  person?.displayGivenName ?? '';
            const birthYr   =  person?.birthYear;
            const deathYr   =  person?.isLiving ? 'Living' : person?.deathYear;
            const years     = [birthYr, deathYr].filter(Boolean).join('–');

            const fs    = gen === 1 ? 13 : gen === 2 ? 11.5 : gen === 3 ? 10 : gen === 4 ? 8.5 : 7.5;
            const lineH = fs * 1.3;

            const maxCh = useRadial
              ? Math.max(5, Math.floor(RING_W * 0.9 / (fs * 0.58)))
              : Math.max(5, Math.round(span * 1.6));

            const showGiven = useRadial ? (span >= 3 && !!givenName) : (span >= 12 && !!givenName);
            const showYears = !useRadial && span >= 8 && !!years;

            const dGiven   = givenName.length > maxCh ? givenName.slice(0, maxCh - 1) + '…' : givenName;
            const dSurname = surname.length   > maxCh ? surname.slice(0, maxCh - 1)   + '…' : surname;

            type Line = { txt: string; bold: boolean; dy: number };
            const lines: Line[] = [];
            let totalH = 0;
            if (showGiven)  { lines.push({ txt: dGiven,   bold: false, dy: 0 }); totalH += lineH; }
                              lines.push({ txt: dSurname, bold: true,  dy: 0 }); totalH += lineH;
            if (showYears)  { lines.push({ txt: years,    bold: false, dy: 0 }); totalH += lineH * 0.9; }
            let cur = -totalH / 2 + lineH * 0.5;
            for (const line of lines) { line.dy = cur; cur += lineH; }

            return (
              <g key={personId}>
                <path
                  className="fan-wedge"
                  d={wedgePath(CX, CY, rIn, rOut, a1, a2)}
                  fill={color}
                  stroke="#ffffff"
                  strokeWidth={1.5}
                  onMouseEnter={(e) =>
                    setTooltip({ clientX: e.clientX, clientY: e.clientY, personId, gen })
                  }
                  onMouseMove={(e) =>
                    setTooltip((prev) =>
                      prev ? { ...prev, clientX: e.clientX, clientY: e.clientY } : null
                    )
                  }
                  onMouseLeave={() => setTooltip(null)}
                />
                <g
                  transform={`translate(${f(tx)},${f(ty)}) rotate(${f(rotation)})`}
                  style={{ pointerEvents: 'none' }}
                >
                  {lines.map(({ txt, bold, dy }, i) => (
                    <text
                      key={i}
                      textAnchor="middle"
                      dy={f(dy)}
                      fontSize={bold ? fs : fs * 0.9}
                      fontWeight={bold ? '700' : '400'}
                      fill="#1a202c"
                      style={{ fontFamily: 'system-ui,sans-serif', userSelect: 'none' }}
                    >
                      {txt}
                    </text>
                  ))}
                </g>
              </g>
            );
          })}

          {/* ── Dividing line ── */}
          {hasAncestors && (
            <line
              x1={CX} y1={CY - FOCUS_R}
              x2={CX} y2={CY - maxR}
              stroke="#ffffff" strokeWidth={1.5} strokeDasharray="4 3"
              style={{ pointerEvents: 'none' }}
            />
          )}

          {/* ── Centre circle (focus person) ── */}
          <circle
            className="fan-focus"
            cx={CX} cy={CY} r={FOCUS_R}
            fill="#e2ddd3" stroke="#ffffff" strokeWidth={2}
          />

          {focusPerson ? (
            <g style={{ pointerEvents: 'none' }}>
              <text
                x={CX} y={CY - (focusYears ? 10 : 0)}
                textAnchor="middle"
                fontSize={13}
                fontWeight="600"
                fill="#2d3748"
                style={{ fontFamily: 'system-ui,sans-serif', userSelect: 'none' }}
              >
                {focusPerson.displayGivenName}
              </text>
              <text
                x={CX} y={CY + 6}
                textAnchor="middle"
                fontSize={13}
                fontWeight="700"
                fill="#1a202c"
                style={{ fontFamily: 'system-ui,sans-serif', userSelect: 'none' }}
              >
                {focusPerson.displaySurname?.toUpperCase() ?? ''}
              </text>
              {focusYears && (
                <text
                  x={CX} y={CY + 22}
                  textAnchor="middle"
                  fontSize={10.5}
                  fill="#4a5568"
                  style={{ fontFamily: 'system-ui,sans-serif', userSelect: 'none' }}
                >
                  {focusYears}
                </text>
              )}
            </g>
          ) : (
            <text x={CX} y={CY + 5} textAnchor="middle" fontSize={12} fill="#718096"
              style={{ fontFamily: 'system-ui,sans-serif', userSelect: 'none', pointerEvents: 'none' }}>
              No focus person
            </text>
          )}

          {/* ── Empty state hint ── */}
          {!hasAncestors && focusPerson && (
            <text
              x={CX} y={CY - FOCUS_R - 20}
              textAnchor="middle"
              fontSize={13}
              fill="#718096"
              style={{ fontFamily: 'system-ui,sans-serif', userSelect: 'none', pointerEvents: 'none' }}
            >
              No ancestors found for this person
            </text>
          )}
        </svg>
      </div>

      {/* ── Tooltip (portal to body so React Flow transforms don't affect it) ── */}
      {tooltip && tooltipPerson && createPortal(
        <div
          style={{
            position:      'fixed',
            left:          tooltip.clientX + 14,
            top:           tooltip.clientY - 10,
            background:    '#1e2533',
            color:         '#f0f4ff',
            padding:       '7px 11px',
            borderRadius:  7,
            fontSize:      13,
            lineHeight:    1.45,
            pointerEvents: 'none',
            whiteSpace:    'nowrap',
            zIndex:        99999,
            boxShadow:     '0 4px 14px rgba(0,0,0,0.45)',
            userSelect:    'none',
          }}
        >
          {/* Name */}
          <div style={{ fontWeight: 700, fontSize: 14 }}>
            {[tooltipPerson.displayGivenName, tooltipPerson.displaySurname]
              .filter(Boolean)
              .join(' ')}
          </div>

          {/* Generation label */}
          <div style={{ fontSize: 11.5, opacity: 0.72, marginTop: 2 }}>
            {genLabel(tooltip.gen)}
            {tooltipYears ? ` · ${tooltipYears}` : ''}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
