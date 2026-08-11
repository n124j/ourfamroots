import type { TFunction } from 'i18next';
import type { RelationshipType } from '@features/tree/types';

export interface RelationshipDirectionOption {
  key: string;
  relationshipType: RelationshipType;
  /** True if the anchor person (whose profile this modal was opened from) is person1 — the role holder. */
  anchorIsPerson1: boolean;
  label: string;
}

/** Options for the "Add relationship" type selector — each pairs a relationship_type with a direction. */
export function relationshipDirectionOptions(t: TFunction): RelationshipDirectionOption[] {
  return [
    { key: 'GODPARENT_FWD', relationshipType: 'GODPARENT', anchorIsPerson1: true, label: t('treeForm.godparentOf') },
    { key: 'GODPARENT_REV', relationshipType: 'GODPARENT', anchorIsPerson1: false, label: t('treeForm.godchildOf') },
    { key: 'GUARDIAN_FWD', relationshipType: 'GUARDIAN', anchorIsPerson1: true, label: t('treeForm.guardianOf') },
    { key: 'GUARDIAN_REV', relationshipType: 'GUARDIAN', anchorIsPerson1: false, label: t('treeForm.wardOf') },
    { key: 'MENTOR_FWD', relationshipType: 'MENTOR', anchorIsPerson1: true, label: t('treeForm.mentorOf') },
    { key: 'MENTOR_REV', relationshipType: 'MENTOR', anchorIsPerson1: false, label: t('treeForm.menteeOf') },
    { key: 'CUSTOM', relationshipType: 'CUSTOM', anchorIsPerson1: true, label: t('treeForm.customRelationship') },
  ];
}

/** Display label for a relationship row shown on `viewerPersonId`'s profile. */
export function relationshipRowLabel(
  t: TFunction,
  rel: { relationship_type: RelationshipType; person1_id: string; custom_label: string | null },
  viewerPersonId: string,
): string {
  if (rel.relationship_type === 'CUSTOM') {
    return rel.custom_label || t('treeForm.customRelationship');
  }
  const viewerIsPerson1 = rel.person1_id === viewerPersonId;
  const forwardKey: Record<string, string> = { GODPARENT: 'godparentOf', GUARDIAN: 'guardianOf', MENTOR: 'mentorOf' };
  const reverseKey: Record<string, string> = { GODPARENT: 'godchildOf', GUARDIAN: 'wardOf', MENTOR: 'menteeOf' };
  const key = viewerIsPerson1 ? forwardKey[rel.relationship_type] : reverseKey[rel.relationship_type];
  return t(`treeForm.${key}`);
}

/**
 * Label for the canvas edge, always read in the natural person1 → person2
 * direction (the edge's source → target) — e.g. "Godparent of" pointing
 * from the Godparent's node to the Godchild's node.
 */
export function relationshipEdgeLabel(
  t: TFunction,
  rel: { relationship_type: RelationshipType; person1_id: string; custom_label: string | null },
): string {
  return relationshipRowLabel(t, rel, rel.person1_id);
}
