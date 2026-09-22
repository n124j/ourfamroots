/**
 * Offline, client-side first-name → Sex confidence guess. No third-party
 * network calls: nameGenderData.json (~18k names, aggregated from public
 * name-frequency data across countries; ambiguous "M;F" source rows split
 * their count evenly between the two sexes) is a same-origin static asset,
 * dynamically imported so it's only fetched once the add-person form is
 * actually used rather than bloating every page's initial bundle.
 *
 * Only returns a guess when one sex accounts for at least
 * CONFIDENCE_THRESHOLD of a name's aggregated usage — otherwise null,
 * leaving the Sex field for the user to set themselves.
 */

const CONFIDENCE_THRESHOLD = 0.75;

// name (lower-cased) -> [maleCount, femaleCount]
type NameGenderData = Record<string, [number, number]>;

let dataPromise: Promise<NameGenderData> | null = null;

function loadData(): Promise<NameGenderData> {
  if (!dataPromise) {
    dataPromise = import('./nameGenderData.json').then((mod) => mod.default as unknown as NameGenderData);
  }
  return dataPromise;
}

export type SexGuess = 'MALE' | 'FEMALE';

export async function guessSexFromFirstName(firstName: string): Promise<SexGuess | null> {
  const key = firstName.trim().toLowerCase();
  if (!key) return null;

  const data = await loadData();
  const entry = data[key];
  if (!entry) return null;

  const [male, female] = entry;
  const total = male + female;
  if (total <= 0) return null;

  const maleShare = male / total;
  if (maleShare >= CONFIDENCE_THRESHOLD) return 'MALE';
  if (1 - maleShare >= CONFIDENCE_THRESHOLD) return 'FEMALE';
  return null;
}
