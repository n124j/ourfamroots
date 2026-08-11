/**
 * Unit tests for RelationshipEdge's fixed visual style — one consistent
 * violet dashed treatment for every relationship type (the label carries
 * the distinction, not the stroke), matching the pattern in
 * UnionEdge.orthogonal.test.tsx (constants/pure-logic, no component mount).
 */
import { STROKE_COLOR, DASH_ARRAY, relationshipEdgeStrokeWidth } from '@features/tree/canvas/edges/RelationshipEdge';

describe('RelationshipEdge style constants', () => {
  it('uses a violet stroke color, distinct from union (amber/green/indigo) and parent-child (theme) colors', () => {
    expect(STROKE_COLOR).toBe('#8b5cf6');
  });

  it('is always dashed — never a solid line like BIOLOGICAL parentage or MARRIAGE unions', () => {
    expect(DASH_ARRAY).not.toBe('solid');
    expect(DASH_ARRAY).toBeTruthy();
  });
});

describe('relationshipEdgeStrokeWidth', () => {
  it('is thicker when selected', () => {
    expect(relationshipEdgeStrokeWidth(true)).toBeGreaterThan(relationshipEdgeStrokeWidth(false));
  });

  it('default (unselected) width is 1.5', () => {
    expect(relationshipEdgeStrokeWidth(false)).toBe(1.5);
  });

  it('selected width is 3', () => {
    expect(relationshipEdgeStrokeWidth(true)).toBe(3);
  });
});
