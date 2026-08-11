/**
 * Unit tests for relationshipEdgeLabel — the label shown on the canvas
 * relationship line, always read in the person1 → person2 (source → target)
 * direction, regardless of who happens to be "viewing" (unlike
 * relationshipRowLabel, which is viewer-relative for the profile modal).
 */
import { relationshipEdgeLabel } from '@features/tree/relationships/labels';
import '../../i18n';
import i18n from '../../i18n';

const t = i18n.getFixedT('en');

function rel(overrides: Partial<Parameters<typeof relationshipEdgeLabel>[1]> = {}) {
  return {
    relationship_type: 'GODPARENT' as const,
    person1_id: 'alice',
    custom_label: null,
    ...overrides,
  };
}

describe('relationshipEdgeLabel', () => {
  it('GODPARENT reads "Godparent of" (the forward/person1 direction)', () => {
    expect(relationshipEdgeLabel(t, rel({ relationship_type: 'GODPARENT' }))).toBe('Godparent of');
  });

  it('GUARDIAN reads "Guardian of"', () => {
    expect(relationshipEdgeLabel(t, rel({ relationship_type: 'GUARDIAN' }))).toBe('Guardian of');
  });

  it('MENTOR reads "Mentor of"', () => {
    expect(relationshipEdgeLabel(t, rel({ relationship_type: 'MENTOR' }))).toBe('Mentor of');
  });

  it('CUSTOM uses the custom_label verbatim', () => {
    expect(relationshipEdgeLabel(t, rel({ relationship_type: 'CUSTOM', custom_label: 'Business Partner' }))).toBe('Business Partner');
  });

  it('CUSTOM falls back to a generic label when custom_label is blank', () => {
    expect(relationshipEdgeLabel(t, rel({ relationship_type: 'CUSTOM', custom_label: null }))).toBe('Custom relationship');
  });

  it('never reads the reverse direction, regardless of which id is passed as person1_id', () => {
    // relationshipEdgeLabel always treats rel.person1_id as the "viewer" internally,
    // so it always returns the forward label — there is no reverse case for edges.
    const a = relationshipEdgeLabel(t, rel({ relationship_type: 'GODPARENT', person1_id: 'alice' }));
    const b = relationshipEdgeLabel(t, rel({ relationship_type: 'GODPARENT', person1_id: 'bob' }));
    expect(a).toBe('Godparent of');
    expect(b).toBe('Godparent of');
  });
});
