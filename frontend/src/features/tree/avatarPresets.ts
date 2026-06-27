/**
 * Person avatar presets.
 *
 * Stored in the DB as "preset:N" in photo_url.
 * Each preset is a simple inline SVG data URI — no server round-trip needed.
 */

export interface AvatarPreset {
  id: string;          // "preset:1" etc.
  label: string;
  bg: string;          // background colour for the card avatar fallback circle
  svg: string;         // inline SVG string
}

function makeSvg(bg: string, pathFill: string, headR = 9, bodyPath: string) {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40">` +
    `<rect width="40" height="40" rx="20" fill="${bg}"/>` +
    `<circle cx="20" cy="15" r="${headR}" fill="${pathFill}"/>` +
    `<path d="${bodyPath}" fill="${pathFill}"/>` +
    `</svg>`
  );
}

const PERSON_BODY  = 'M6 40c0-7.7 6.3-14 14-14s14 6.3 14 14';
const CHILD_BODY   = 'M9 40c0-6.1 4.9-11 11-11s11 4.9 11 11';
const ELDER_BODY   = 'M7 40c0-7.2 5.8-13 13-13s13 5.8 13 13';

export const AVATAR_PRESETS: AvatarPreset[] = [
  {
    id: 'preset:1', label: 'Person',
    bg: '#3b82f6',
    svg: makeSvg('#3b82f6', 'rgba(255,255,255,0.92)', 9, PERSON_BODY),
  },
  {
    id: 'preset:2', label: 'Person',
    bg: '#ec4899',
    svg: makeSvg('#ec4899', 'rgba(255,255,255,0.92)', 9, PERSON_BODY),
  },
  {
    id: 'preset:3', label: 'Child',
    bg: '#f59e0b',
    svg: makeSvg('#f59e0b', 'rgba(255,255,255,0.92)', 7, CHILD_BODY),
  },
  {
    id: 'preset:4', label: 'Child',
    bg: '#10b981',
    svg: makeSvg('#10b981', 'rgba(255,255,255,0.92)', 7, CHILD_BODY),
  },
  {
    id: 'preset:5', label: 'Elder',
    bg: '#6366f1',
    svg: makeSvg('#6366f1', 'rgba(255,255,255,0.92)', 9, ELDER_BODY),
  },
  {
    id: 'preset:6', label: 'Elder',
    bg: '#8b5cf6',
    svg: makeSvg('#8b5cf6', 'rgba(255,255,255,0.92)', 9, ELDER_BODY),
  },
  {
    id: 'preset:7', label: 'Person',
    bg: '#0ea5e9',
    svg: makeSvg('#0ea5e9', 'rgba(255,255,255,0.92)', 9, PERSON_BODY),
  },
  {
    id: 'preset:8', label: 'Person',
    bg: '#f97316',
    svg: makeSvg('#f97316', 'rgba(255,255,255,0.92)', 9, PERSON_BODY),
  },
];

export const PRESET_MAP = new Map(AVATAR_PRESETS.map((p) => [p.id, p]));

/** Returns true when photo_url is a preset reference. */
export function isPreset(url: string | undefined): boolean {
  return !!url?.startsWith('preset:');
}

/** Returns an <img>-ready data URI for the preset, or undefined. */
export function presetDataUri(presetId: string): string | undefined {
  const p = PRESET_MAP.get(presetId);
  if (!p) return undefined;
  return `data:image/svg+xml;base64,${btoa(p.svg)}`;
}
