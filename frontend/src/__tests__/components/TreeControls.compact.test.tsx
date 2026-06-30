/**
 * Unit tests for TreeControls compact-mode switching logic.
 *
 * Tests the handleCompactView decision logic in isolation (no DOM/React render),
 * following the same pattern as TreeCanvas.test.tsx.
 *
 * Covers:
 *  - Plain click always activates 'compact'
 *  - Shift+click while in 'descendant-family' activates 'compact-descendant-family'
 *  - Shift+click while already in 'compact-descendant-family' stays in it (toggle-back guard)
 *  - Shift+click while in 'ancestor-family' activates 'compact-ancestor-family'   ← NEW
 *  - Shift+click while already in 'compact-ancestor-family' stays in it            ← NEW
 *  - Shift+click in any other mode falls through to plain 'compact'
 *  - LAYOUT_MODES active-state logic: ancestor-family button highlights when compact-ancestor-family is active
 *  - Compact button active-state covers all three compact variants
 */

import type { LayoutMode } from '@features/tree/types';

// ── Mirror of handleCompactView from TreeControls.tsx ─────────────────────────

function applyCompactClick(layoutMode: LayoutMode, shiftKey: boolean): LayoutMode {
  if (shiftKey && (layoutMode === 'descendant-family' || layoutMode === 'compact-descendant-family')) {
    return 'compact-descendant-family';
  } else if (shiftKey && (layoutMode === 'ancestor-family' || layoutMode === 'compact-ancestor-family')) {
    return 'compact-ancestor-family';
  } else {
    return 'compact';
  }
}

// ── Mirror of LAYOUT_MODES onClick logic ──────────────────────────────────────

function applyLayoutModeClick(
  mode: LayoutMode,
  layoutMode: LayoutMode,
  shiftKey: boolean,
): LayoutMode {
  if (
    mode === 'descendant-family' &&
    shiftKey &&
    (layoutMode === 'compact' || layoutMode === 'compact-descendant-family')
  ) {
    return 'compact-descendant-family';
  } else if (
    mode === 'ancestor-family' &&
    shiftKey &&
    (layoutMode === 'compact' || layoutMode === 'compact-ancestor-family')
  ) {
    return 'compact-ancestor-family';
  } else {
    return mode;
  }
}

// ── Mirror of Compact-button active state ─────────────────────────────────────

function isCompactButtonActive(layoutMode: LayoutMode): boolean {
  return (
    layoutMode === 'compact' ||
    layoutMode === 'compact-descendant-family' ||
    layoutMode === 'compact-ancestor-family'
  );
}

// ── Mirror of LAYOUT_MODES active-state ───────────────────────────────────────

function isLayoutModeButtonActive(mode: LayoutMode, layoutMode: LayoutMode): boolean {
  return (
    layoutMode === mode ||
    (mode === 'descendant-family' && layoutMode === 'compact-descendant-family') ||
    (mode === 'ancestor-family'   && layoutMode === 'compact-ancestor-family')
  );
}

// ── handleCompactView tests ────────────────────────────────────────────────────

describe('handleCompactView — plain click', () => {
  const nonCompactModes: LayoutMode[] = [
    'generation', 'vertical', 'horizontal', 'ancestor', 'descendant',
    'descendant-family', 'ancestor-family', 'fan', 'ancestry-fan', 'pedigree',
  ];

  it('always returns compact on a plain (no-shift) click', () => {
    for (const mode of nonCompactModes) {
      expect(applyCompactClick(mode, false)).toBe('compact');
    }
  });

  it('returns compact when already in compact and clicking again (no-shift)', () => {
    expect(applyCompactClick('compact', false)).toBe('compact');
  });

  it('returns compact on no-shift even from compact-descendant-family', () => {
    expect(applyCompactClick('compact-descendant-family', false)).toBe('compact');
  });

  it('returns compact on no-shift even from compact-ancestor-family', () => {
    expect(applyCompactClick('compact-ancestor-family', false)).toBe('compact');
  });
});

describe('handleCompactView — Shift+click for descendants', () => {
  it('Shift+click in descendant-family activates compact-descendant-family', () => {
    expect(applyCompactClick('descendant-family', true)).toBe('compact-descendant-family');
  });

  it('Shift+click while already in compact-descendant-family stays in compact-descendant-family', () => {
    expect(applyCompactClick('compact-descendant-family', true)).toBe('compact-descendant-family');
  });
});

describe('handleCompactView — Shift+click for ancestors (new)', () => {
  it('Shift+click in ancestor-family activates compact-ancestor-family', () => {
    expect(applyCompactClick('ancestor-family', true)).toBe('compact-ancestor-family');
  });

  it('Shift+click while already in compact-ancestor-family stays in compact-ancestor-family', () => {
    expect(applyCompactClick('compact-ancestor-family', true)).toBe('compact-ancestor-family');
  });
});

describe('handleCompactView — Shift+click in other modes falls through to compact', () => {
  const otherModes: LayoutMode[] = [
    'generation', 'vertical', 'horizontal', 'ancestor', 'descendant',
    'fan', 'ancestry-fan', 'pedigree', 'compact',
  ];

  it('Shift+click in a non-family mode returns compact', () => {
    for (const mode of otherModes) {
      expect(applyCompactClick(mode, true)).toBe('compact');
    }
  });
});

// ── LAYOUT_MODES onClick tests ─────────────────────────────────────────────────

describe('LAYOUT_MODES onClick — descendant-family Shift+click', () => {
  it('Shift+click on descendant-family button when compact is active → compact-descendant-family', () => {
    expect(applyLayoutModeClick('descendant-family', 'compact', true)).toBe('compact-descendant-family');
  });

  it('Shift+click on descendant-family when compact-descendant-family is active → compact-descendant-family', () => {
    expect(applyLayoutModeClick('descendant-family', 'compact-descendant-family', true)).toBe('compact-descendant-family');
  });

  it('plain click on descendant-family always switches to descendant-family', () => {
    expect(applyLayoutModeClick('descendant-family', 'compact', false)).toBe('descendant-family');
    expect(applyLayoutModeClick('descendant-family', 'generation', false)).toBe('descendant-family');
  });

  it('Shift+click on descendant-family when some other mode is active → descendant-family', () => {
    // shiftKey is true but current mode is not compact — no special handling
    expect(applyLayoutModeClick('descendant-family', 'generation', true)).toBe('descendant-family');
  });
});

describe('LAYOUT_MODES onClick — ancestor-family Shift+click (new)', () => {
  it('Shift+click on ancestor-family button when compact is active → compact-ancestor-family', () => {
    expect(applyLayoutModeClick('ancestor-family', 'compact', true)).toBe('compact-ancestor-family');
  });

  it('Shift+click on ancestor-family when compact-ancestor-family is active → compact-ancestor-family', () => {
    expect(applyLayoutModeClick('ancestor-family', 'compact-ancestor-family', true)).toBe('compact-ancestor-family');
  });

  it('plain click on ancestor-family always switches to ancestor-family', () => {
    expect(applyLayoutModeClick('ancestor-family', 'compact', false)).toBe('ancestor-family');
    expect(applyLayoutModeClick('ancestor-family', 'generation', false)).toBe('ancestor-family');
  });

  it('Shift+click on ancestor-family when some other mode is active → ancestor-family', () => {
    expect(applyLayoutModeClick('ancestor-family', 'generation', true)).toBe('ancestor-family');
  });
});

// ── Compact button active-state ────────────────────────────────────────────────

describe('Compact button active state', () => {
  it('is active when layoutMode is compact', () => {
    expect(isCompactButtonActive('compact')).toBe(true);
  });

  it('is active when layoutMode is compact-descendant-family', () => {
    expect(isCompactButtonActive('compact-descendant-family')).toBe(true);
  });

  it('is active when layoutMode is compact-ancestor-family', () => {
    expect(isCompactButtonActive('compact-ancestor-family')).toBe(true);
  });

  it('is not active for regular layout modes', () => {
    const inactive: LayoutMode[] = [
      'generation', 'vertical', 'horizontal', 'ancestor', 'descendant',
      'descendant-family', 'ancestor-family', 'fan', 'ancestry-fan', 'pedigree',
    ];
    for (const mode of inactive) {
      expect(isCompactButtonActive(mode)).toBe(false);
    }
  });
});

// ── LAYOUT_MODES active-state ─────────────────────────────────────────────────

describe('LAYOUT_MODES button active states', () => {
  it('descendant-family button is active when mode is compact-descendant-family', () => {
    expect(isLayoutModeButtonActive('descendant-family', 'compact-descendant-family')).toBe(true);
  });

  it('descendant-family button is not active for compact-ancestor-family', () => {
    expect(isLayoutModeButtonActive('descendant-family', 'compact-ancestor-family')).toBe(false);
  });

  it('ancestor-family button is active when mode is compact-ancestor-family (new)', () => {
    expect(isLayoutModeButtonActive('ancestor-family', 'compact-ancestor-family')).toBe(true);
  });

  it('ancestor-family button is not active for compact-descendant-family', () => {
    expect(isLayoutModeButtonActive('ancestor-family', 'compact-descendant-family')).toBe(false);
  });

  it('each button is active for its own exact mode', () => {
    const modes: LayoutMode[] = [
      'generation', 'vertical', 'horizontal', 'ancestor', 'descendant',
      'descendant-family', 'ancestor-family', 'fan', 'ancestry-fan', 'pedigree',
    ];
    for (const mode of modes) {
      expect(isLayoutModeButtonActive(mode, mode)).toBe(true);
    }
  });

  it('no cross-contamination between unrelated modes', () => {
    expect(isLayoutModeButtonActive('ancestor-family', 'descendant-family')).toBe(false);
    expect(isLayoutModeButtonActive('descendant-family', 'ancestor-family')).toBe(false);
    expect(isLayoutModeButtonActive('compact-ancestor-family' as LayoutMode, 'compact-descendant-family')).toBe(false);
  });
});
