/**
 * Unit tests for PersonNode's change-request diff presentation helpers —
 * the color/badge logic that highlights added/modified persons when
 * reviewing a proposal in tree form.
 */
import {
  DIFF_STATUS_COLOR,
  diffBadgeGlyph,
  diffBadgeTitle,
  diffStatusColor,
} from '@features/tree/canvas/nodes/PersonNode';

describe('diffStatusColor', () => {
  it('returns green for an added person', () => {
    expect(diffStatusColor('added')).toBe(DIFF_STATUS_COLOR.added);
  });

  it('returns amber for a modified person', () => {
    expect(diffStatusColor('modified')).toBe(DIFF_STATUS_COLOR.modified);
  });

  it('returns null when there is no diff status (normal tree browsing)', () => {
    expect(diffStatusColor(undefined)).toBeNull();
  });

  it('added and modified use visibly different colors', () => {
    expect(DIFF_STATUS_COLOR.added).not.toBe(DIFF_STATUS_COLOR.modified);
  });
});

describe('diffBadgeGlyph', () => {
  it('shows a plus for added', () => {
    expect(diffBadgeGlyph('added')).toBe('+');
  });

  it('shows a pencil for modified', () => {
    expect(diffBadgeGlyph('modified')).toBe('✎');
  });
});

describe('diffBadgeTitle', () => {
  it('describes an added person', () => {
    expect(diffBadgeTitle('added')).toMatch(/new/i);
  });

  it('describes a modified person', () => {
    expect(diffBadgeTitle('modified')).toMatch(/modified/i);
  });
});
