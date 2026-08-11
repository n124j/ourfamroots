import { get, post, del } from '@api/client';
import type { ApiRelationship, RelationshipType } from '@features/tree/types';

export interface CreateRelationshipBody {
  person1_id: string;
  person2_id: string;
  relationship_type: RelationshipType;
  custom_label?: string | null;
  notes?: string | null;
}

export function fetchRelationships(treeId: string): Promise<ApiRelationship[]> {
  return get<ApiRelationship[]>(`/trees/${treeId}/relationships`);
}

export function createRelationship(treeId: string, body: CreateRelationshipBody): Promise<ApiRelationship> {
  return post<ApiRelationship>(`/trees/${treeId}/relationships`, body);
}

export function deleteRelationship(treeId: string, relationshipId: string): Promise<void> {
  return del(`/trees/${treeId}/relationships/${relationshipId}`);
}
