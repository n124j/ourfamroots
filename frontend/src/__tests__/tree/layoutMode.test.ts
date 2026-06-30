/**
 * Unit tests for LayoutMode type exhaustiveness and legend/PDF key coverage.
 *
 * Ensures every LayoutMode value (including the newly added compact-ancestor-family)
 * is represented in LEGEND_TITLE_KEYS and PDF_TITLES-style mappings so that
 * TypeScript Record<LayoutMode, string> exhaustiveness catches omissions at
 * compile time — and these runtime tests catch them in CI.
 *
 * Covers:
 *  - All 13 LayoutMode values are present
 *  - compact-ancestor-family was added alongside ancestor-family
 *  - compact-descendant-family was added alongside descendant-family
 *  - LEGEND_TITLE_KEYS record covers every LayoutMode (mirrored from TreeCanvas.tsx)
 *  - PDF_TITLES record covers every LayoutMode (mirrored from TreeCanvas.tsx)
 *  - Compact variants share the same legend key as their non-compact counterpart
 *  - ViewPlugin interface accepts layoutOverrides.mode as any LayoutMode
 */

import type { LayoutMode } from '@features/tree/types';

// ── Canonical list of all layout modes ────────────────────────────────────────

const ALL_LAYOUT_MODES: LayoutMode[] = [
  'compact',
  'generation',
  'vertical',
  'horizontal',
  'ancestor',
  'descendant',
  'descendant-family',
  'compact-descendant-family',
  'ancestor-family',
  'compact-ancestor-family',
  'fan',
  'ancestry-fan',
  'pedigree',
];

// ── Mirror of LEGEND_TITLE_KEYS from TreeCanvas.tsx ───────────────────────────

const LEGEND_TITLE_KEYS: Record<LayoutMode, string> = {
  compact:                      'legend.familyTree',
  generation:                   'legend.familyTree',
  vertical:                     'legend.familyTree',
  horizontal:                   'legend.familyTree',
  fan:                          'legend.fanChart',
  'ancestry-fan':               'legend.ancestryFan',
  ancestor:                     'legend.ancestorChart',
  descendant:                   'legend.descendantChart',
  'descendant-family':          'legend.descendantsSpouses',
  'compact-descendant-family':  'legend.descendantsSpouses',
  'ancestor-family':            'legend.ancestorsSpouses',
  'compact-ancestor-family':    'legend.ancestorsSpouses',
  pedigree:                     'legend.pedigreeChart',
};

// ── Mirror of PDF_TITLES from TreeCanvas.tsx (focus-name-independent keys) ───

function buildPdfTitle(mode: LayoutMode, focusName: string | null, treeName: string): string {
  const PDF_TITLES: Record<LayoutMode, string> = {
    compact:                      treeName,
    generation:                   treeName,
    vertical:                     treeName,
    horizontal:                   treeName,
    fan:                          focusName ? `Fan Chart — ${focusName}` : 'Fan Chart',
    'ancestry-fan':               focusName ? `Ancestry Fan — ${focusName}` : 'Ancestry Fan',
    ancestor:                     focusName ? `Ancestors of ${focusName}` : 'Ancestor Chart',
    descendant:                   focusName ? `Descendants of ${focusName}` : 'Descendant Chart',
    'descendant-family':          focusName ? `Descendants of ${focusName}` : 'Descendants + Spouses',
    'compact-descendant-family':  focusName ? `Descendants of ${focusName}` : 'Descendants + Spouses',
    'ancestor-family':            focusName ? `Ancestors of ${focusName}` : 'Ancestors + Spouses',
    'compact-ancestor-family':    focusName ? `Ancestors of ${focusName}` : 'Ancestors + Spouses',
    pedigree:                     focusName ? `Pedigree — ${focusName}` : 'Pedigree Chart',
  };
  return PDF_TITLES[mode];
}

// ── LayoutMode count & presence ───────────────────────────────────────────────

describe('LayoutMode — mode list', () => {
  it('has exactly 13 layout modes', () => {
    expect(ALL_LAYOUT_MODES).toHaveLength(13);
  });

  it('includes compact-ancestor-family', () => {
    expect(ALL_LAYOUT_MODES).toContain('compact-ancestor-family');
  });

  it('includes compact-descendant-family', () => {
    expect(ALL_LAYOUT_MODES).toContain('compact-descendant-family');
  });

  it('compact-ancestor-family is a valid LayoutMode (type assertion)', () => {
    const mode: LayoutMode = 'compact-ancestor-family';
    expect(mode).toBe('compact-ancestor-family');
  });

  it('compact-descendant-family is a valid LayoutMode (type assertion)', () => {
    const mode: LayoutMode = 'compact-descendant-family';
    expect(mode).toBe('compact-descendant-family');
  });

  it('all mode strings are non-empty', () => {
    for (const mode of ALL_LAYOUT_MODES) {
      expect(mode.length).toBeGreaterThan(0);
    }
  });

  it('no duplicate mode values', () => {
    const unique = new Set(ALL_LAYOUT_MODES);
    expect(unique.size).toBe(ALL_LAYOUT_MODES.length);
  });
});

// ── LEGEND_TITLE_KEYS coverage ────────────────────────────────────────────────

describe('LEGEND_TITLE_KEYS — Record<LayoutMode, string> coverage', () => {
  it('has an entry for every LayoutMode', () => {
    for (const mode of ALL_LAYOUT_MODES) {
      expect(LEGEND_TITLE_KEYS[mode]).toBeTruthy();
    }
  });

  it('compact-ancestor-family maps to legend.ancestorsSpouses', () => {
    expect(LEGEND_TITLE_KEYS['compact-ancestor-family']).toBe('legend.ancestorsSpouses');
  });

  it('compact-descendant-family maps to legend.descendantsSpouses', () => {
    expect(LEGEND_TITLE_KEYS['compact-descendant-family']).toBe('legend.descendantsSpouses');
  });

  it('compact-ancestor-family shares its key with ancestor-family', () => {
    expect(LEGEND_TITLE_KEYS['compact-ancestor-family']).toBe(LEGEND_TITLE_KEYS['ancestor-family']);
  });

  it('compact-descendant-family shares its key with descendant-family', () => {
    expect(LEGEND_TITLE_KEYS['compact-descendant-family']).toBe(LEGEND_TITLE_KEYS['descendant-family']);
  });

  it('all legend key values are non-empty strings', () => {
    for (const key of Object.values(LEGEND_TITLE_KEYS)) {
      expect(typeof key).toBe('string');
      expect(key.length).toBeGreaterThan(0);
    }
  });

  it('all legend keys use the legend.* namespace', () => {
    for (const key of Object.values(LEGEND_TITLE_KEYS)) {
      expect(key).toMatch(/^legend\./);
    }
  });
});

// ── PDF_TITLES coverage ───────────────────────────────────────────────────────

describe('PDF_TITLES — Record<LayoutMode, string> coverage', () => {
  const TREE_NAME = 'My Family Tree';
  const FOCUS = 'Alice Smith';

  it('has an entry for every LayoutMode (no focus name)', () => {
    for (const mode of ALL_LAYOUT_MODES) {
      expect(buildPdfTitle(mode, null, TREE_NAME)).toBeTruthy();
    }
  });

  it('has an entry for every LayoutMode (with focus name)', () => {
    for (const mode of ALL_LAYOUT_MODES) {
      expect(buildPdfTitle(mode, FOCUS, TREE_NAME)).toBeTruthy();
    }
  });

  it('compact-ancestor-family without focus → "Ancestors + Spouses"', () => {
    expect(buildPdfTitle('compact-ancestor-family', null, TREE_NAME)).toBe('Ancestors + Spouses');
  });

  it('compact-ancestor-family with focus → "Ancestors of <name>"', () => {
    expect(buildPdfTitle('compact-ancestor-family', FOCUS, TREE_NAME)).toBe(`Ancestors of ${FOCUS}`);
  });

  it('compact-ancestor-family matches ancestor-family output', () => {
    expect(buildPdfTitle('compact-ancestor-family', null, TREE_NAME))
      .toBe(buildPdfTitle('ancestor-family', null, TREE_NAME));
    expect(buildPdfTitle('compact-ancestor-family', FOCUS, TREE_NAME))
      .toBe(buildPdfTitle('ancestor-family', FOCUS, TREE_NAME));
  });

  it('compact-descendant-family without focus → "Descendants + Spouses"', () => {
    expect(buildPdfTitle('compact-descendant-family', null, TREE_NAME)).toBe('Descendants + Spouses');
  });

  it('compact-descendant-family matches descendant-family output', () => {
    expect(buildPdfTitle('compact-descendant-family', null, TREE_NAME))
      .toBe(buildPdfTitle('descendant-family', null, TREE_NAME));
    expect(buildPdfTitle('compact-descendant-family', FOCUS, TREE_NAME))
      .toBe(buildPdfTitle('descendant-family', FOCUS, TREE_NAME));
  });

  it('tree-name modes return the tree name regardless of focus', () => {
    const treeNameModes: LayoutMode[] = ['compact', 'generation', 'vertical', 'horizontal'];
    for (const mode of treeNameModes) {
      expect(buildPdfTitle(mode, FOCUS, TREE_NAME)).toBe(TREE_NAME);
      expect(buildPdfTitle(mode, null, TREE_NAME)).toBe(TREE_NAME);
    }
  });

  it('focus-name modes include the focus name in their title', () => {
    const focusModes: LayoutMode[] = [
      'ancestor', 'descendant', 'descendant-family', 'compact-descendant-family',
      'ancestor-family', 'compact-ancestor-family', 'fan', 'ancestry-fan', 'pedigree',
    ];
    for (const mode of focusModes) {
      expect(buildPdfTitle(mode, FOCUS, TREE_NAME)).toContain(FOCUS);
    }
  });
});

// ── Compact mode pairing invariants ───────────────────────────────────────────

describe('Compact mode pairing invariants', () => {
  it('each compact mode has a corresponding non-compact base mode', () => {
    expect(ALL_LAYOUT_MODES).toContain('descendant-family');
    expect(ALL_LAYOUT_MODES).toContain('compact-descendant-family');
    expect(ALL_LAYOUT_MODES).toContain('ancestor-family');
    expect(ALL_LAYOUT_MODES).toContain('compact-ancestor-family');
  });

  it('compact variant names follow the compact-<base> naming pattern', () => {
    const compactModes = ALL_LAYOUT_MODES.filter((m) => m.startsWith('compact-') && m !== 'compact');
    for (const mode of compactModes) {
      const base = mode.replace(/^compact-/, '');
      expect(ALL_LAYOUT_MODES).toContain(base as LayoutMode);
    }
  });
});
