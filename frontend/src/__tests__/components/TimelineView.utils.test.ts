/**
 * Unit tests for TimelineView year-parsing utilities.
 *
 * These functions are internal to TimelineView.tsx and are replicated here to
 * allow pure-logic testing without mounting the component (which depends on
 * Vite-specific store and canvas context providers).
 *
 * The implementations below MUST stay in sync with the originals in
 * src/features/tree/canvas/TimelineView.tsx. If those change, update here.
 *
 * Covers:
 *  - parseYear()        — coerces raw values to a valid year int or undefined
 *  - resolveBirthYear() — reads birthYear (number) then falls back to birthDate string
 *  - resolveDeathYear() — same pattern for death dates
 *  - Person bar color mapping by sex
 *  - Lifespan string construction (birth – death / present / ?)
 */

// ── Replicate pure utility functions from TimelineView.tsx ────────────────────

function parseYear(raw: unknown): number | undefined {
  if (raw == null) return undefined;
  const n = typeof raw === 'number' ? raw : parseInt(String(raw), 10);
  return !isNaN(n) && n > 100 ? n : undefined; // >100 AD filters zeros/garbage
}

interface MinimalPerson {
  birthYear?: number | string;
  birthDate?: string;
  deathYear?: number | string;
  deathDate?: string;
}

function resolveBirthYear(p: MinimalPerson): number | undefined {
  const fromYear = parseYear((p as any).birthYear);
  if (fromYear !== undefined) return fromYear;
  if (p.birthDate) return parseYear(p.birthDate.slice(0, 4));
  return undefined;
}

function resolveDeathYear(p: MinimalPerson): number | undefined {
  const fromYear = parseYear((p as any).deathYear);
  if (fromYear !== undefined) return fromYear;
  if (p.deathDate) return parseYear(p.deathDate.slice(0, 4));
  return undefined;
}

// ── parseYear ─────────────────────────────────────────────────────────────────

describe('parseYear', () => {
  it('returns a number when given a valid year integer', () => {
    expect(parseYear(1950)).toBe(1950);
    expect(parseYear(2000)).toBe(2000);
    expect(parseYear(101)).toBe(101);
  });

  it('parses a numeric string', () => {
    expect(parseYear('1950')).toBe(1950);
    expect(parseYear('2024')).toBe(2024);
  });

  it('returns undefined for null or undefined', () => {
    expect(parseYear(null)).toBeUndefined();
    expect(parseYear(undefined)).toBeUndefined();
  });

  it('returns undefined for values ≤ 100 (garbage filter)', () => {
    expect(parseYear(0)).toBeUndefined();
    expect(parseYear(100)).toBeUndefined();
    expect(parseYear(-1)).toBeUndefined();
    expect(parseYear(50)).toBeUndefined();
  });

  it('returns undefined for non-numeric strings', () => {
    expect(parseYear('not-a-year')).toBeUndefined();
    expect(parseYear('')).toBeUndefined();
    expect(parseYear('abc')).toBeUndefined();
  });

  it('returns undefined for NaN', () => {
    expect(parseYear(NaN)).toBeUndefined();
  });

  it('returns undefined for an object', () => {
    expect(parseYear({})).toBeUndefined();
  });

  it('handles year 101 as the minimum valid year', () => {
    expect(parseYear(101)).toBe(101);
    expect(parseYear(100)).toBeUndefined();
  });
});

// ── resolveBirthYear ──────────────────────────────────────────────────────────

describe('resolveBirthYear', () => {
  it('returns birthYear when it is a valid number', () => {
    expect(resolveBirthYear({ birthYear: 1950 })).toBe(1950);
  });

  it('returns birthYear when it arrives as a string (runtime coercion)', () => {
    expect(resolveBirthYear({ birthYear: '1950' as any })).toBe(1950);
  });

  it('falls back to birthDate year when birthYear is absent', () => {
    expect(resolveBirthYear({ birthDate: '1985-03-15' })).toBe(1985);
  });

  it('falls back to birthDate year when birthYear is undefined', () => {
    expect(resolveBirthYear({ birthYear: undefined, birthDate: '1972-07-04' })).toBe(1972);
  });

  it('birthYear takes priority over birthDate when both are present', () => {
    expect(resolveBirthYear({ birthYear: 1960, birthDate: '1972-07-04' })).toBe(1960);
  });

  it('returns undefined when neither birthYear nor birthDate is present', () => {
    expect(resolveBirthYear({})).toBeUndefined();
  });

  it('returns undefined when birthDate has an unparseable year prefix', () => {
    expect(resolveBirthYear({ birthDate: 'bad-date' })).toBeUndefined();
  });

  it('handles 4-digit year-only birthDate strings', () => {
    expect(resolveBirthYear({ birthDate: '1900' })).toBe(1900);
  });
});

// ── resolveDeathYear ──────────────────────────────────────────────────────────

describe('resolveDeathYear', () => {
  it('returns deathYear when it is a valid number', () => {
    expect(resolveDeathYear({ deathYear: 2020 })).toBe(2020);
  });

  it('falls back to deathDate year when deathYear is absent', () => {
    expect(resolveDeathYear({ deathDate: '2005-11-22' })).toBe(2005);
  });

  it('returns undefined when neither deathYear nor deathDate is present', () => {
    expect(resolveDeathYear({})).toBeUndefined();
  });

  it('deathYear takes priority over deathDate', () => {
    expect(resolveDeathYear({ deathYear: 1999, deathDate: '2005-11-22' })).toBe(1999);
  });

  it('handles deathYear as string (runtime coercion)', () => {
    expect(resolveDeathYear({ deathYear: '2001' as any })).toBe(2001);
  });
});

// ── Lifespan string construction ──────────────────────────────────────────────

describe('Timeline lifespan display logic', () => {
  function lifespan(
    birthYear: number | undefined,
    deathYear: number | undefined,
    isLiving = false,
  ): string | null {
    if (!birthYear) return null;
    const deathStr = deathYear != null ? String(deathYear) : isLiving ? 'present' : '?';
    return `${birthYear} – ${deathStr}`;
  }

  it('returns null when birth year is unknown', () => {
    expect(lifespan(undefined, undefined)).toBeNull();
  });

  it('shows birth – death for a deceased person with known death year', () => {
    expect(lifespan(1900, 1980)).toBe('1900 – 1980');
  });

  it('shows birth – present for a living person with no death year', () => {
    expect(lifespan(1970, undefined, true)).toBe('1970 – present');
  });

  it('shows birth – ? when deceased but death year unknown', () => {
    expect(lifespan(1900, undefined, false)).toBe('1900 – ?');
  });
});

// ── Sex bar color mapping ─────────────────────────────────────────────────────

describe('Timeline sex bar color mapping', () => {
  const SEX_BAR_COLORS: Record<string, { bar: string; text: string }> = {
    MALE:    { bar: '#4a90b8', text: '#ffffff' },
    FEMALE:  { bar: '#b05070', text: '#ffffff' },
    OTHER:   { bar: '#8b5cf6', text: '#ffffff' },
    UNKNOWN: { bar: '#94a3b8', text: '#ffffff' },
  };

  it('all sex values have bar and text colors', () => {
    for (const sex of ['MALE', 'FEMALE', 'OTHER', 'UNKNOWN']) {
      expect(SEX_BAR_COLORS[sex]).toBeDefined();
      expect(SEX_BAR_COLORS[sex].bar).toMatch(/^#[0-9a-f]{6}$/i);
      expect(SEX_BAR_COLORS[sex].text).toBe('#ffffff');
    }
  });

  it('falls back to UNKNOWN color for unrecognised sex values', () => {
    const sex = 'ALIEN';
    const color = SEX_BAR_COLORS[sex] ?? SEX_BAR_COLORS.UNKNOWN;
    expect(color.bar).toBe('#94a3b8');
  });
});
