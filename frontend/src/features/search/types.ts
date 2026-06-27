export interface PersonHit {
  person_id: string;
  tree_id: string;
  given_name?: string | null;
  surname?: string | null;
  maiden_name?: string | null;
  birth_year?: number | null;
  death_year?: number | null;
  birth_place?: string | null;
  is_living: boolean;
  score: number;
}

export interface AncestorHit {
  person_id: string;
  given_name?: string | null;
  surname?: string | null;
  birth_year?: number | null;
  death_year?: number | null;
  depth: number;
  relationship_label: string;
  is_living: boolean;
}

export interface PathStep {
  person_id: string;
  name: string;
  sex?: string | null;
}

export interface RelationshipPath {
  found: boolean;
  distance: number;
  path: PathStep[];
  relationship_label?: string | null;
  alternative_label?: string | null;
  edge_labels?: string[];
}

export interface NameSearchResponse {
  total: number;
  hits: PersonHit[];
  took_ms: number;
}

export interface GraphSearchResponse {
  total: number;
  items: AncestorHit[];
  took_ms: number;
}

export interface RelationshipResponse {
  relationship: RelationshipPath;
  took_ms: number;
}

export interface SearchFilters {
  birth_year_min?: number;
  birth_year_max?: number;
  birth_place?: string;
  sort?: 'relevance' | 'name' | 'birth_year' | 'updated_at';
  fuzzy?: boolean;
}
