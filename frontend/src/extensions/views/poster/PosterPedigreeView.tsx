/**
 * PosterPedigreeView — decorative, print-ready ancestor chart.
 *
 * Centred on a couple (the focus person + their spouse) sitting side by side,
 * with ONE bare-tree image (public/tree-bg.png) rising behind them, trunk
 * centred on the couple: the focus person's own ancestors fan out beneath
 * the left side of the canopy, their spouse's beneath the right — one
 * cohesive tree, not two separate ones with a gap between them. If the
 * couple has children recorded together, their first names appear in a box
 * below the couple. If the focus person has no recorded spouse, it falls
 * back to a single tree split by the focus person's own two parents
 * (paternal line left, maternal right).
 *
 * Boxes for ancestors not yet recorded are left blank, like a fillable
 * template, so the poster still looks complete while research continues.
 * Names are always shown in full (never truncated) — the font shrinks to fit
 * long names instead.
 *
 * Uses the existing Export PDF button (top toolbar) to print/save — it
 * screenshots whatever canvas view is active, including this one.
 */

import React, { memo, useEffect, useMemo, useRef, useState } from 'react';
import type { ApiTreeGraph, ApiPerson, Sex } from '@features/tree/types';
import { useCanvasStore } from '@store/canvas.store';
import { isPreset, presetDataUri } from '@features/tree/avatarPresets';
import { PosterOrnament } from './PosterOrnament';

// Real bare-tree artwork (frontend/public/tree-bg.png), background made
// transparent and cropped tight to its bounding box so the trunk's bottom
// edge lines up exactly with the bottom of the image.
const TREE_IMG_SRC = '/tree-bg.png';
const TREE_IMG_ASPECT = 1405 / 1059; // width / height

const DEFAULT_GENERATIONS = 4;
const MIN_GENERATIONS = 2;
const MAX_GENERATIONS = 6;

const MIN_ZOOM = 0.4;
const MAX_ZOOM = 2.5;
const ZOOM_STEP = 1.25;

const BOX_W = 170;
const BOX_H = 34;
const BOX_GAP = 14;
const COUPLE_GAP = 10; // gap between the two boxes of a couple
const CHILDREN_BOX_W = BOX_W * 1.9;
const ROW_PITCH = 68;
const TOP_MARGIN = 170;   // room for title + ornament
const BOTTOM_MARGIN = 60;
const SIDE_MARGIN = 60;

const INK = '#2b241c';
const PAPER = '#f4f1ea';
const BOX_FILL = '#fdfcf8';
const BOX_STROKE = '#8a7c68';

function personName(p: ApiPerson | undefined): string {
  if (!p) return '';
  return [p.displayGivenName, p.displaySurname].filter(Boolean).join(' ');
}

function parseYear(raw: unknown): number | undefined {
  if (raw == null) return undefined;
  const n = typeof raw === 'number' ? raw : parseInt(String(raw), 10);
  return !isNaN(n) && n > 100 ? n : undefined;
}

function lifespan(p: ApiPerson | undefined): string {
  if (!p) return '';
  const birth = parseYear(p.birthYear) ?? (p.birthDate ? parseYear(p.birthDate.slice(0, 4)) : undefined);
  const death = parseYear(p.deathYear) ?? (p.deathDate ? parseYear(p.deathDate.slice(0, 4)) : undefined);
  if (!birth && !death) return '';
  return `${birth ?? '?'}–${death ?? (p.isLiving ? 'present' : '?')}`;
}

/**
 * Full names are always shown (never truncated) — instead the font shrinks
 * to fit the box width, only going below `min` for pathologically long names
 * (which then simply overflow the box edges slightly rather than being cut).
 */
function fitFontSize(text: string, boxWidth: number, base: number, min = 8): number {
  if (!text) return base;
  const usable = boxWidth - 16;
  const avgCharWidth = 0.54; // approx. glyph width ratio for EB Garamond serif
  const needed = text.length * avgCharWidth * base;
  if (needed <= usable) return base;
  return Math.max(min, usable / (text.length * avgCharWidth));
}

/** Joins first names the way a poster caption would: "A", "A and B", "A, B, and C". */
function joinFirstNames(names: string[]): string {
  if (names.length === 0) return '';
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(', ')}, and ${names[names.length - 1]}`;
}

function resolvePhotoUrl(p: ApiPerson | undefined): string | undefined {
  if (!p?.photoUrl) return undefined;
  return isPreset(p.photoUrl) ? presetDataUri(p.photoUrl) : p.photoUrl;
}

interface HoverInfo { person: ApiPerson; rect: DOMRect }

/** Tooltip shown on hover — name + profile photo, if any. */
function PosterTooltip({ info }: { info: HoverInfo }) {
  const { person, rect } = info;
  const name = personName(person) || 'Unknown';
  const life = lifespan(person);
  const photoUrl = resolvePhotoUrl(person);

  const TOOLTIP_W = 220;
  const TOOLTIP_H = 76;
  const top = rect.top - TOOLTIP_H - 8 >= 8 ? rect.top - TOOLTIP_H - 8 : rect.bottom + 8;
  const left = Math.min(Math.max(rect.left + rect.width / 2 - TOOLTIP_W / 2, 8), window.innerWidth - TOOLTIP_W - 8);

  return (
    <div
      style={{
        position: 'fixed', top, left, width: TOOLTIP_W, zIndex: 9999,
        background: '#fffdf9', border: `1px solid ${BOX_STROKE}`, borderRadius: 10,
        boxShadow: '0 8px 24px rgba(0,0,0,0.25)', padding: '10px 12px',
        pointerEvents: 'none', display: 'flex', gap: 10, alignItems: 'center',
      }}
    >
      <div
        style={{
          width: 44, height: 44, borderRadius: '50%', overflow: 'hidden', flexShrink: 0,
          background: '#efe9dd', border: `2px solid ${BOX_STROKE}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
      >
        {photoUrl ? (
          <img src={photoUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        ) : (
          <span style={{ fontSize: 18, fontWeight: 700, color: '#6b5d4a' }}>{name[0]?.toUpperCase() ?? '?'}</span>
        )}
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: INK, fontFamily: '"EB Garamond", serif' }}>{name}</div>
        {life && <div style={{ fontSize: 11, color: '#5a5040', marginTop: 2 }}>{life}</div>}
      </div>
    </div>
  );
}

/** Ranks parents so the father (if known) renders on the left, mother on the right. */
function sortParents(ids: string[], personById: Map<string, ApiPerson>): [string | null, string | null] {
  const rank = (id: string) => {
    const sex: Sex | undefined = personById.get(id)?.sex;
    return sex === 'MALE' ? 0 : sex === 'FEMALE' ? 1 : 2;
  };
  const sorted = [...ids].sort((a, b) => rank(a) - rank(b));
  return [sorted[0] ?? null, sorted[1] ?? null];
}

function parentsOf(
  personId: string | null,
  personParentFG: Map<string, string>,
  fgById: Map<string, ApiTreeGraph['familyGroups'][number]>,
  personById: Map<string, ApiPerson>,
): [string | null, string | null] {
  if (!personId) return [null, null];
  const fgId = personParentFG.get(personId);
  const fg = fgId ? fgById.get(fgId) : undefined;
  if (!fg) return [null, null];
  const ids = fg.parentIds.filter((id) => personById.has(id));
  return sortParents(ids, personById);
}

/** First recorded spouse/partner of `personId` (any union type), if any. */
function findSpouse(
  personId: string,
  graph: ApiTreeGraph,
  personById: Map<string, ApiPerson>,
): string | null {
  for (const fg of graph.familyGroups) {
    if (!fg.parentIds.includes(personId)) continue;
    const other = fg.parentIds.find((id) => id !== personId);
    if (other && personById.has(other)) return other;
  }
  return null;
}

/** Children recorded under the specific union between `aId` and `bId`. */
function findCoupleChildren(
  aId: string,
  bId: string,
  graph: ApiTreeGraph,
  personById: Map<string, ApiPerson>,
): ApiPerson[] {
  const fg = graph.familyGroups.find((f) => f.parentIds.includes(aId) && f.parentIds.includes(bId));
  if (!fg) return [];
  return Object.keys(fg.children)
    .map((id) => personById.get(id))
    .filter((p): p is ApiPerson => !!p);
}

interface AncestorGrid {
  /** key `${half}:${gen}:${slot}` -> personId | null */
  cells: Map<string, string | null>;
}

/**
 * Builds one ancestor fan per half. `leftSeed`/`rightSeed` are that half's
 * generation-1 occupants directly (a couple's own two parents, or — in the
 * no-spouse fallback — a single already-known person), so both the "two full
 * trees" and "one tree split by parent" shapes share this same builder.
 */
function buildAncestorGrid(
  leftSeed: (string | null)[],
  rightSeed: (string | null)[],
  maxGen: number,
  personParentFG: Map<string, string>,
  fgById: Map<string, ApiTreeGraph['familyGroups'][number]>,
  personById: Map<string, ApiPerson>,
): AncestorGrid {
  const cells = new Map<string, string | null>();
  const seeds: Record<'-1' | '1', (string | null)[]> = { '-1': leftSeed, '1': rightSeed };

  for (const half of [-1, 1] as const) {
    let frontier: (string | null)[] = seeds[String(half) as '-1' | '1'];
    for (let gen = 1; gen <= maxGen; gen++) {
      frontier.forEach((pid, slot) => cells.set(`${half}:${gen}:${slot}`, pid));
      if (gen === maxGen) break;
      const next: (string | null)[] = [];
      for (const pid of frontier) {
        const [f, m] = parentsOf(pid, personParentFG, fgById, personById);
        next.push(f, m);
      }
      frontier = next;
    }
  }

  return { cells };
}

interface PosterPedigreeViewProps {
  graph: ApiTreeGraph;
}

function PosterPedigreeViewComponent({ graph }: PosterPedigreeViewProps) {
  const focusPersonId = useCanvasStore((s) => s.focusPersonId);
  const isPdfMode = useCanvasStore((s) => s.isPdfMode);
  const [maxGen, setMaxGen] = useState(DEFAULT_GENERATIONS);
  const [hovered, setHovered] = useState<HoverInfo | null>(null);
  const [zoom, setZoom] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pendingScrollRef = useRef<{ left: number; top: number } | null>(null);
  const dragStartRef = useRef<{ x: number; y: number; scrollLeft: number; scrollTop: number } | null>(null);

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

  const spouseId = useMemo(
    () => (rootId ? findSpouse(rootId, graph, personById) : null),
    [rootId, graph, personById],
  );
  const hasSpouse = !!spouseId;

  const children = useMemo(
    () => (rootId && spouseId ? findCoupleChildren(rootId, spouseId, graph, personById) : []),
    [rootId, spouseId, graph, personById],
  );
  const hasChildren = children.length > 0;
  const childrenLabel = joinFirstNames(children.map((c) => c.displayGivenName || 'Unknown'));

  const { leftSeed, rightSeed } = useMemo(() => {
    if (!rootId) return { leftSeed: [] as (string | null)[], rightSeed: [] as (string | null)[] };
    if (spouseId) {
      return {
        leftSeed: parentsOf(rootId, personParentFG, fgById, personById),
        rightSeed: parentsOf(spouseId, personParentFG, fgById, personById),
      };
    }
    const [father, mother] = parentsOf(rootId, personParentFG, fgById, personById);
    return { leftSeed: [father], rightSeed: [mother] };
  }, [rootId, spouseId, personParentFG, fgById, personById]);

  // Couple mode seeds 2 people per half at gen1 (the person's own father +
  // mother); the no-spouse fallback seeds just 1 (matching the old "split a
  // single root's two parents across both halves" shape). Every deeper
  // generation still doubles from there.
  const seedLen = Math.max(1, leftSeed.length);

  const grid = useMemo(
    () => buildAncestorGrid(leftSeed, rightSeed, maxGen, personParentFG, fgById, personById),
    [leftSeed, rightSeed, maxGen, personParentFG, fgById, personById],
  );

  // Classic column-based pedigree layout (same maths as the app's existing
  // `pedigreeChart.ts`): each generation is a vertical COLUMN one step
  // further out; within a column, every person sits exactly halfway between
  // their own two parents in the next column out, via the standard
  // "halving" trick — a fixed total slot range is divided into fewer, wider
  // bands for shallow generations and more, narrower bands for deep ones,
  // so nothing ever overlaps and the focus person always ends up vertically
  // centred among their own ancestors.
  function slotsAtGen(gen: number): number {
    return seedLen * Math.pow(2, gen - 1);
  }
  const numSlotsAtMax = slotsAtGen(maxGen);
  const SLOT_PAD = 20; // vertical gap between adjacent boxes at the deepest generation
  const SLOT_H = BOX_H + SLOT_PAD;
  const COL_GAP = 50; // horizontal gap between generation columns
  const COL_PITCH = BOX_W + COL_GAP;
  const fanHalfHeight = (numSlotsAtMax * SLOT_H) / 2;

  const coupleOffset = hasSpouse ? BOX_W / 2 + COUPLE_GAP / 2 : 0;
  const contentWidth = 2 * (coupleOffset + maxGen * COL_PITCH) + BOX_W + SIDE_MARGIN * 2;
  const centerX = contentWidth / 2;
  // The couple (gen0) sits at the vertical centre of their own ancestor
  // fans, which is what makes the focus person appear "centred on screen"
  // rather than pinned to the bottom.
  const coupleY = TOP_MARGIN + fanHalfHeight;
  const contentHeight = coupleY + fanHalfHeight + BOTTOM_MARGIN + (hasChildren ? ROW_PITCH : 0);
  const bottomY = contentHeight - BOTTOM_MARGIN;

  // Re-rooting or changing the generation count starts fresh at 100% zoom.
  useEffect(() => { setZoom(1); }, [maxGen, rootId, spouseId]);

  // Bring the couple to the centre of the viewport on load/generation/zoom
  // change — without this the view opens scrolled to the top-left corner and
  // the couple (the whole point of the poster) is nowhere on screen. A wheel
  // zoom sets `pendingScrollRef` first so it can keep the point under the
  // cursor fixed instead of re-centring on the couple.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (pendingScrollRef.current) {
      el.scrollLeft = Math.max(0, pendingScrollRef.current.left);
      el.scrollTop = Math.max(0, pendingScrollRef.current.top);
      pendingScrollRef.current = null;
    } else {
      el.scrollLeft = Math.max(0, centerX * zoom - el.clientWidth / 2);
      el.scrollTop = Math.max(0, coupleY * zoom - el.clientHeight / 2);
    }
  }, [zoom, centerX, coupleY, maxGen, rootId, spouseId]);

  // Wheel-to-zoom, centred on the cursor. Attached as a native listener
  // (rather than a JSX onWheel) because React attaches wheel handlers as
  // passive by default, which silently ignores preventDefault() and lets
  // the page scroll instead of zooming.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el || isPdfMode) return;
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const rect = el!.getBoundingClientRect();
      const viewX = e.clientX - rect.left;
      const viewY = e.clientY - rect.top;
      setZoom((current) => {
        const contentX = (el!.scrollLeft + viewX) / current;
        const contentY = (el!.scrollTop + viewY) / current;
        const factor = Math.exp(-e.deltaY * 0.0015);
        const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current * factor));
        pendingScrollRef.current = { left: contentX * next - viewX, top: contentY * next - viewY };
        return next;
      });
    }
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [isPdfMode]);

  // Click-and-drag panning. Listeners on `window` (not the container) so a
  // drag keeps tracking even if the cursor leaves the canvas mid-drag.
  useEffect(() => {
    if (!isDragging) return;
    function onMove(e: MouseEvent) {
      const el = scrollRef.current;
      const start = dragStartRef.current;
      if (!el || !start) return;
      el.scrollLeft = start.scrollLeft - (e.clientX - start.x);
      el.scrollTop = start.scrollTop - (e.clientY - start.y);
    }
    function onUp() {
      dragStartRef.current = null;
      setIsDragging(false);
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [isDragging]);

  function handleCanvasMouseDown(e: React.MouseEvent) {
    if (isPdfMode) return;
    const el = scrollRef.current;
    if (!el) return;
    e.preventDefault(); // avoid native text-selection while dragging over box labels
    dragStartRef.current = { x: e.clientX, y: e.clientY, scrollLeft: el.scrollLeft, scrollTop: el.scrollTop };
    setIsDragging(true);
  }

  function zoomBy(factor: number) {
    setZoom((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z * factor)));
  }

  /** x-position of the couple/root box that a half's generation-1 boxes connect down to. */
  function anchorBoxX(half: -1 | 1): number {
    return centerX + half * coupleOffset;
  }
  function boxX(half: -1 | 1, gen: number): number {
    return anchorBoxX(half) + half * gen * COL_PITCH;
  }
  function boxY(gen: number, slot: number): number {
    if (gen <= 0) return coupleY;
    const slotsPerPerson = numSlotsAtMax / slotsAtGen(gen);
    const yCen = (slot + 0.5) * slotsPerPerson * SLOT_H;
    return coupleY - fanHalfHeight + yCen;
  }

  if (!rootId) {
    return (
      <div className="w-full h-full flex items-center justify-center" style={{ background: PAPER }}>
        <p className="text-sm" style={{ color: INK }}>No people in this tree yet.</p>
      </div>
    );
  }

  const rootPerson = personById.get(rootId);
  const spousePerson = spouseId ? personById.get(spouseId) : undefined;

  // Flatten grid into renderable boxes + right-angle connector lines to
  // their child box, edge-to-edge (child's outward edge → midpoint →
  // parent's inward edge) — the classic pedigree-chart step-line style.
  const boxes: { key: string; x: number; y: number; person: ApiPerson | undefined }[] = [];
  const connectors: { key: string; x1: number; y1: number; midX: number; x2: number; y2: number }[] = [];

  for (const half of [-1, 1] as const) {
    for (let gen = 1; gen <= maxGen; gen++) {
      const nSlots = slotsAtGen(gen);
      for (let slot = 0; slot < nSlots; slot++) {
        const personId = grid.cells.get(`${half}:${gen}:${slot}`) ?? null;
        const person = personId ? personById.get(personId) : undefined;
        const x = boxX(half, gen);
        const y = boxY(gen, slot);
        boxes.push({ key: `${half}:${gen}:${slot}`, x, y, person });

        // Connector to the child box one generation closer to the root.
        const childX = boxX(half, gen - 1);
        const childY = boxY(gen - 1, Math.floor(slot / 2));
        const childEdgeX = childX + half * (BOX_W / 2);
        const parentEdgeX = x - half * (BOX_W / 2);
        connectors.push({
          key: `line-${half}:${gen}:${slot}`,
          x1: childEdgeX, y1: childY,
          midX: (childEdgeX + parentEdgeX) / 2,
          x2: parentEdgeX, y2: y,
        });
      }
    }
  }

  // Connector from the couple down to their children's box, if any.
  const childrenConnectors = hasChildren
    ? ([-1, 1] as const).map((half) => ({
        key: `children-line-${half}`,
        x1: anchorBoxX(half), y1: coupleY + BOX_H / 2,
        x2: centerX, y2: bottomY - BOX_H / 2,
        midY: (coupleY + bottomY) / 2,
      }))
    : [];

  // ONE big tree image, trunk rooted at the bottom-most middle box (the
  // children's box when there is one, otherwise the couple's own row),
  // filling essentially the full height from just below the title down to
  // that base — tall enough that its canopy rises well above the
  // generation-1 ancestor boxes on both sides. Width simply follows from
  // the source art's aspect ratio, only capped so it can't blow past the
  // poster's own width on very shallow trees. Ancestor/couple/children
  // boxes are drawn AFTER this image (see below), so it's fine for the
  // canopy to visually extend behind/past them — the opaque box fills keep
  // every name legible on top of it.
  const treeBaseY = (hasChildren ? bottomY : coupleY) + BOX_H / 2 + 6;
  const treeAvailHeight = Math.max(60, treeBaseY - (TOP_MARGIN - 20));
  let treeImgHeight = treeAvailHeight;
  let treeImgWidth = treeImgHeight * TREE_IMG_ASPECT;
  const maxTreeImgWidth = contentWidth - SIDE_MARGIN;
  if (treeImgWidth > maxTreeImgWidth) {
    treeImgWidth = maxTreeImgWidth;
    treeImgHeight = treeImgWidth / TREE_IMG_ASPECT;
  }
  const treeImgX = centerX - treeImgWidth / 2;
  const treeImgY = treeBaseY - treeImgHeight;

  const headerName = hasSpouse
    ? `${personName(rootPerson) || 'Unknown'} & ${personName(spousePerson) || 'Unknown'}`
    : personName(rootPerson) || 'Unknown';

  /**
   * `emphasized` boxes (the couple) always show a name — falling back to
   * "Unknown" is fine since a real person is guaranteed there. Ordinary
   * ancestor boxes must stay visually BLANK when nothing is recorded, so the
   * poster still reads as a fillable template rather than a wall of
   * "Unknown"s.
   */
  function renderPersonBox(key: string, x: number, y: number, name: string, life: string, emphasized: boolean, width: number, person?: ApiPerson) {
    const displayName = emphasized ? (name || 'Unknown') : name;
    return (
      <g
        key={key}
        style={{ cursor: person ? 'pointer' : 'default' }}
        onMouseEnter={(e) =>
          person && setHovered({ person, rect: (e.currentTarget as SVGGElement).getBoundingClientRect() })
        }
        onMouseLeave={() => setHovered(null)}
      >
        <rect
          x={x - width / 2} y={y - BOX_H / 2}
          width={width} height={BOX_H} rx={5}
          fill={BOX_FILL}
          stroke={emphasized ? INK : BOX_STROKE}
          strokeWidth={emphasized ? 1.8 : 1.2}
        />
        {displayName && (
          <text
            x={x} y={life ? y - 3 : y + 4}
            textAnchor="middle"
            style={{
              fontFamily: '"EB Garamond", serif',
              fontSize: fitFontSize(displayName, width, emphasized ? 14 : 13),
              fill: INK, fontWeight: emphasized ? 700 : 600,
            }}
          >
            {displayName}
          </text>
        )}
        {life && (
          <text
            x={x} y={y + 13}
            textAnchor="middle"
            style={{ fontFamily: '"EB Garamond", serif', fontSize: 10, fill: '#5a5040' }}
          >
            {life}
          </text>
        )}
      </g>
    );
  }

  return (
    <div className="w-full h-full flex flex-col" style={{ background: PAPER }}>
      {!isPdfMode && (
        <div className="flex items-center gap-3 px-4 py-2.5 shrink-0 bg-white border-b border-slate-200">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Family Tree Poster</p>
            <p className="text-sm font-medium text-slate-700 truncate">
              {headerName}'s Family Tree
            </p>
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-500">Generations</span>
            <button
              onClick={() => setMaxGen((d) => Math.max(MIN_GENERATIONS, d - 1))}
              className="w-6 h-6 rounded-md text-xs font-bold flex items-center justify-center border border-slate-200 text-slate-600 bg-white hover:bg-slate-50"
              title="Fewer generations"
            >
              −
            </button>
            <span className="text-xs font-mono w-4 text-center text-slate-700">{maxGen}</span>
            <button
              onClick={() => setMaxGen((d) => Math.min(MAX_GENERATIONS, d + 1))}
              className="w-6 h-6 rounded-md text-xs font-bold flex items-center justify-center border border-slate-200 text-slate-600 bg-white hover:bg-slate-50"
              title="More generations"
            >
              +
            </button>
          </div>
          <div className="flex items-center gap-1.5 pl-3 ml-1 border-l border-slate-200">
            <button
              onClick={() => zoomBy(1 / ZOOM_STEP)}
              className="w-6 h-6 rounded-md text-xs font-bold flex items-center justify-center border border-slate-200 text-slate-600 bg-white hover:bg-slate-50"
              title="Zoom out"
            >
              −
            </button>
            <span className="text-xs font-mono w-10 text-center text-slate-700">{Math.round(zoom * 100)}%</span>
            <button
              onClick={() => zoomBy(ZOOM_STEP)}
              className="w-6 h-6 rounded-md text-xs font-bold flex items-center justify-center border border-slate-200 text-slate-600 bg-white hover:bg-slate-50"
              title="Zoom in"
            >
              +
            </button>
            <button
              onClick={() => setZoom(1)}
              className="px-2 h-6 rounded-md text-xs font-medium flex items-center justify-center border border-slate-200 text-slate-600 bg-white hover:bg-slate-50"
              title="Reset zoom"
            >
              Reset
            </button>
          </div>
        </div>
      )}

      {/* PDF export needs the full unclipped content size — overflow:auto would
          otherwise cap the capture at whatever fits in the on-screen viewport.
          Deliberately NOT using flex centering here: `justify-content: center`
          on an overflowing flex item bakes in its own implicit scroll offset
          that then compounds with the scrollLeft/scrollTop set below, landing
          nowhere near the intended position. Plain block layout + JS-driven
          scroll position is simpler and predictable. */}
      <div
        ref={scrollRef}
        onMouseDown={handleCanvasMouseDown}
        className={isPdfMode ? '' : 'flex-1 min-h-0 overflow-auto'}
        style={isPdfMode ? undefined : { cursor: isDragging ? 'grabbing' : 'grab', userSelect: 'none' }}
      >
        {/* Wrapper sized to the zoomed footprint so scrollbars/scrollLeft-Top
            track the visually scaled content; the SVG itself keeps its
            original width/height (and thus crisp internal layout maths) and
            is scaled purely via CSS transform. */}
        <div style={{ width: contentWidth * (isPdfMode ? 1 : zoom), height: contentHeight * (isPdfMode ? 1 : zoom) }}>
          <svg
            width={contentWidth}
            height={contentHeight}
            viewBox={`0 0 ${contentWidth} ${contentHeight}`}
            style={{
              background: PAPER,
              display: 'block',
              transform: isPdfMode ? undefined : `scale(${zoom})`,
              transformOrigin: 'top left',
            }}
          >
          {/* One tree silhouette, trunk rooted at the bottom-middle box, behind everything */}
          <image
            href={TREE_IMG_SRC}
            x={treeImgX} y={treeImgY}
            width={treeImgWidth} height={treeImgHeight}
          />

          {/* Connector lines */}
          <g stroke={BOX_STROKE} strokeWidth={1} fill="none">
            {connectors.map((c) => (
              <polyline
                key={c.key}
                points={`${c.x1},${c.y1} ${c.midX},${c.y1} ${c.midX},${c.y2} ${c.x2},${c.y2}`}
              />
            ))}
            {childrenConnectors.map((c) => (
              <polyline
                key={c.key}
                points={`${c.x1},${c.y1} ${c.x1},${c.midY} ${c.x2},${c.midY} ${c.x2},${c.y2}`}
              />
            ))}
          </g>

          {/* Title */}
          <text
            x={centerX} y={64}
            textAnchor="middle"
            style={{ fontFamily: '"Great Vibes", cursive', fontSize: 52, fill: INK }}
          >
            My Family Tree
          </text>
          <foreignObject x={centerX - 130} y={78} width={260} height={40}>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <PosterOrnament width={260} color="#6b5d4a" />
            </div>
          </foreignObject>

          {/* Ancestor boxes */}
          {boxes.map((b) =>
            renderPersonBox(b.key, b.x, b.y, personName(b.person), lifespan(b.person), false, BOX_W, b.person),
          )}

          {/* Root box (+ spouse box, side by side, when a couple is found) */}
          {hasSpouse ? (
            <>
              {renderPersonBox('root-box', centerX - coupleOffset, coupleY, personName(rootPerson), lifespan(rootPerson), true, BOX_W, rootPerson)}
              {renderPersonBox('spouse-box', centerX + coupleOffset, coupleY, personName(spousePerson), lifespan(spousePerson), true, BOX_W, spousePerson)}
            </>
          ) : (
            renderPersonBox('root-box', centerX, coupleY, personName(rootPerson), lifespan(rootPerson), true, BOX_W, rootPerson)
          )}

          {/* Children box — first names only, comma-separated */}
          {hasChildren && (
            <g>
              <rect
                x={centerX - CHILDREN_BOX_W / 2} y={bottomY - BOX_H / 2}
                width={CHILDREN_BOX_W} height={BOX_H} rx={5}
                fill={BOX_FILL} stroke={INK} strokeWidth={1.8}
              />
              <text
                x={centerX} y={bottomY + 4}
                textAnchor="middle"
                style={{
                  fontFamily: '"EB Garamond", serif',
                  fontSize: fitFontSize(childrenLabel, CHILDREN_BOX_W, 14),
                  fill: INK, fontWeight: 600,
                }}
              >
                {childrenLabel}
              </text>
            </g>
          )}
          </svg>
        </div>
      </div>

      {!isPdfMode && hovered && <PosterTooltip info={hovered} />}
    </div>
  );
}

export const PosterPedigreeView = memo(PosterPedigreeViewComponent);
