/**
 * Unit tests for guessSexFromFirstName — an offline, client-side first-name
 * to Sex confidence guess used to pre-fill the Sex field when adding a
 * person. No third-party network calls: the dataset (src/shared/nameGenderData.json,
 * ~18k names aggregated from public name-frequency data) is a same-origin
 * static asset, dynamically imported (code-split) on first use — hence the
 * async API.
 */
import { describe, expect, test } from 'vitest';

import { guessSexFromFirstName } from '@shared/guessSexFromName';

describe('guessSexFromFirstName', () => {
  test('returns MALE for a common strongly-male name', async () => {
    expect(await guessSexFromFirstName('James')).toBe('MALE');
  });

  test('returns FEMALE for a common strongly-female name', async () => {
    expect(await guessSexFromFirstName('Emma')).toBe('FEMALE');
  });

  test('is case-insensitive', async () => {
    expect(await guessSexFromFirstName('eMMA')).toBe('FEMALE');
  });

  test('trims surrounding whitespace', async () => {
    expect(await guessSexFromFirstName('  Emma  ')).toBe('FEMALE');
  });

  test('returns null for an unknown name', async () => {
    expect(await guessSexFromFirstName('Xyzzyqplonk')).toBeNull();
  });

  test('returns null for an empty string', async () => {
    expect(await guessSexFromFirstName('')).toBeNull();
  });

  test('returns null for a name with no confident majority sex', async () => {
    expect(await guessSexFromFirstName('Jordan')).toBeNull();
  });

  test('returns null for a name where a M;F source row split the count evenly', async () => {
    expect(await guessSexFromFirstName('Ali')).toBeNull();
  });
});
