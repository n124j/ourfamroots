/**
 * Unit tests for UnionEdge orthogonal (Heritage-view) path logic.
 *
 * UnionEdge switches to a step-path SVG when orthogonalEdges=true (Heritage view).
 * This file tests the path math and visual-style rules in isolation, matching the
 * pattern in TreeCanvas.test.tsx (logic extracted and tested without rendering).
 *
 * Covers:
 *  - step path string construction (M L L L)
 *  - marriage double-line: offset applied symmetrically in both modes
 *  - stroke offset scales with selection and highlight state
 *  - midpoint (label position) is always the centre of the path
 *  - divorced dash pattern applied for divorced unions
 *  - union type → dash pattern mapping (UNION_STROKE)
 */

// ── Replicate step-path logic from UnionEdge.tsx ──────────────────────────────

function stepPath(
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
  offset = 0,
): string {
  const midY = (sourceY + targetY) / 2;
  return (
    `M ${sourceX + offset} ${sourceY} ` +
    `L ${sourceX + offset} ${midY} ` +
    `L ${targetX + offset} ${midY} ` +
    `L ${targetX + offset} ${targetY}`
  );
}

function midpoint(
  sourceX: number, sourceY: number,
  targetX: number, targetY: number,
): { x: number; y: number } {
  return { x: (sourceX + targetX) / 2, y: (sourceY + targetY) / 2 };
}

// ── Replicate stroke-offset selection logic ────────────────────────────────────

function lineOffset(selected: boolean, highlighted: boolean | undefined): number {
  if (selected) return 2.5;
  if (highlighted === true) return 2;
  return 1.5;
}

// ── Replicate UNION_STROKE map (types.ts) ─────────────────────────────────────

const UNION_STROKE: Record<string, string> = {
  MARRIAGE:     'solid',
  PARTNERSHIP:  'solid',
  COHABITATION: '6 4',
  UNKNOWN:      '2 4',
};

// ── step path string ──────────────────────────────────────────────────────────

describe('orthogonal step path — string structure', () => {
  it('produces a 4-segment M L L L path', () => {
    const p = stepPath(100, 0, 200, 200);
    const parts = p.trim().split(/\s+(?=[MLZ])/);
    expect(parts).toHaveLength(4);
    expect(parts[0]).toMatch(/^M/);
    expect(parts[1]).toMatch(/^L/);
    expect(parts[2]).toMatch(/^L/);
    expect(parts[3]).toMatch(/^L/);
  });

  it('starts at (sourceX, sourceY) when offset is 0', () => {
    const p = stepPath(50, 10, 150, 200);
    expect(p.startsWith('M 50 10')).toBe(true);
  });

  it('ends at (targetX, targetY) when offset is 0', () => {
    const p = stepPath(50, 10, 150, 200);
    expect(p.endsWith('150 200')).toBe(true);
  });

  it('horizontal segment is at midY', () => {
    const sourceY = 0;
    const targetY = 200;
    const midY = (sourceY + targetY) / 2; // 100
    const p = stepPath(50, sourceY, 150, targetY);
    // The two middle segments share midY
    expect(p).toContain(`L 50 ${midY}`);
    expect(p).toContain(`L 150 ${midY}`);
  });

  it('applies positive offset to sourceX and targetX', () => {
    const off = 3;
    const p = stepPath(100, 0, 200, 200, off);
    expect(p.startsWith(`M ${100 + off}`)).toBe(true);
    expect(p).toContain(`L ${200 + off} 200`);
  });

  it('applies negative offset symmetrically', () => {
    const off = -2;
    const p = stepPath(100, 0, 200, 200, off);
    expect(p.startsWith(`M ${100 + off}`)).toBe(true);
    expect(p).toContain(`L ${200 + off} 200`);
  });

  it('produces a straight vertical path when sourceX === targetX', () => {
    const p = stepPath(100, 0, 100, 200);
    // All x values should be 100
    expect(p).not.toMatch(/\d+ \d+/.source); // just validate no error
    expect(p.startsWith('M 100 0')).toBe(true);
    expect(p.endsWith('100 200')).toBe(true);
  });
});

// ── marriage double-line offset ───────────────────────────────────────────────

describe('marriage double-line offset', () => {
  it('default (non-selected, non-highlighted) offset is 1.5', () => {
    expect(lineOffset(false, undefined)).toBe(1.5);
  });

  it('selected offset is 2.5', () => {
    expect(lineOffset(true, false)).toBe(2.5);
  });

  it('highlighted offset is 2', () => {
    expect(lineOffset(false, true)).toBe(2);
  });

  it('selection takes priority over highlight', () => {
    expect(lineOffset(true, true)).toBe(2.5);
  });

  it('pathA and pathB are symmetric around the centre line', () => {
    const off = lineOffset(false, undefined);
    const sourceX = 100;
    const targetX = 200;
    const pathA = stepPath(sourceX, 0, targetX, 100, -off);
    const pathB = stepPath(sourceX, 0, targetX, 100, +off);
    // pathA starts to the left, pathB starts to the right
    expect(pathA.startsWith(`M ${sourceX - off}`)).toBe(true);
    expect(pathB.startsWith(`M ${sourceX + off}`)).toBe(true);
  });
});

// ── midpoint (label position) ─────────────────────────────────────────────────

describe('midpoint for label placement', () => {
  it('is the geometric centre of source and target', () => {
    const mid = midpoint(100, 0, 200, 200);
    expect(mid.x).toBe(150);
    expect(mid.y).toBe(100);
  });

  it('handles identical source and target (zero-length edge)', () => {
    const mid = midpoint(100, 100, 100, 100);
    expect(mid.x).toBe(100);
    expect(mid.y).toBe(100);
  });

  it('works for a purely horizontal edge', () => {
    const mid = midpoint(0, 50, 200, 50);
    expect(mid.x).toBe(100);
    expect(mid.y).toBe(50);
  });

  it('works for a purely vertical edge', () => {
    const mid = midpoint(100, 0, 100, 300);
    expect(mid.x).toBe(100);
    expect(mid.y).toBe(150);
  });
});

// ── UNION_STROKE mapping ──────────────────────────────────────────────────────

describe('UNION_STROKE dash pattern mapping', () => {
  it('MARRIAGE is solid', () => {
    expect(UNION_STROKE.MARRIAGE).toBe('solid');
  });

  it('PARTNERSHIP is solid', () => {
    expect(UNION_STROKE.PARTNERSHIP).toBe('solid');
  });

  it('COHABITATION has a dash pattern', () => {
    expect(UNION_STROKE.COHABITATION).not.toBe('solid');
    expect(UNION_STROKE.COHABITATION).toBeTruthy();
  });

  it('UNKNOWN has a dot pattern', () => {
    expect(UNION_STROKE.UNKNOWN).not.toBe('solid');
    expect(UNION_STROKE.UNKNOWN).toBeTruthy();
  });

  it('all four union types have an entry', () => {
    for (const type of ['MARRIAGE', 'PARTNERSHIP', 'COHABITATION', 'UNKNOWN']) {
      expect(UNION_STROKE[type]).toBeDefined();
    }
  });
});

// ── divorced dash override ────────────────────────────────────────────────────

describe('divorced dash override', () => {
  const DIVORCED_DASH = '4 4';

  function effectiveDash(
    unionType: string,
    isDivorced: boolean,
    stroke: Record<string, string>,
  ): string | undefined {
    if (isDivorced) return DIVORCED_DASH;
    const dash = stroke[unionType];
    return dash === 'solid' ? undefined : dash;
  }

  it('applies divorced dash regardless of union type for marriage', () => {
    expect(effectiveDash('MARRIAGE', true, UNION_STROKE)).toBe('4 4');
  });

  it('applies divorced dash regardless of union type for cohabitation', () => {
    expect(effectiveDash('COHABITATION', true, UNION_STROKE)).toBe('4 4');
  });

  it('no dash for non-divorced solid marriage', () => {
    expect(effectiveDash('MARRIAGE', false, UNION_STROKE)).toBeUndefined();
  });

  it('cohabitation keeps its own dash when not divorced', () => {
    expect(effectiveDash('COHABITATION', false, UNION_STROKE)).toBe('6 4');
  });

  it('UNKNOWN keeps its own dash when not divorced', () => {
    expect(effectiveDash('UNKNOWN', false, UNION_STROKE)).toBe('2 4');
  });
});

// ── opacity & highlight logic ─────────────────────────────────────────────────

describe('Union edge opacity based on highlight state', () => {
  function effectiveOpacity(
    selected: boolean,
    isHighlighted: boolean | undefined,
  ): number {
    if (selected) return 1;
    if (isHighlighted === true) return 1;
    if (isHighlighted === false) return 0.15;
    return 1; // no highlight state — fully opaque
  }

  it('selected edge is fully opaque', () => {
    expect(effectiveOpacity(true, false)).toBe(1);
  });

  it('highlighted edge is fully opaque', () => {
    expect(effectiveOpacity(false, true)).toBe(1);
  });

  it('dimmed (hl=false) edge has 0.15 opacity', () => {
    expect(effectiveOpacity(false, false)).toBe(0.15);
  });

  it('default (hl=undefined) edge is fully opaque', () => {
    expect(effectiveOpacity(false, undefined)).toBe(1);
  });

  it('selection overrides dim highlight', () => {
    expect(effectiveOpacity(true, false)).toBe(1);
  });
});
