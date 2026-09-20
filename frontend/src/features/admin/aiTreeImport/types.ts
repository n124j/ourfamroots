export interface ExtractedPerson {
  id: string;
  display_given_name: string;
  display_surname: string;
  sex: 'MALE' | 'FEMALE' | 'OTHER' | 'UNKNOWN';
}

export interface ExtractedFamilyGroup {
  id: string;
  union_type: 'MARRIAGE' | 'PARTNERSHIP' | 'COHABITATION' | 'UNKNOWN';
  parent_ids: string[];
  children: Record<string, string>;
}

export interface ExtractedDraft {
  persons: ExtractedPerson[];
  family_groups: ExtractedFamilyGroup[];
}

export interface UploadUrlResponse {
  job_id: string;
  upload_url: string;
  upload_fields: Record<string, string>;
  max_size_bytes: number;
}

export interface JobStatusResponse {
  job_id: string;
  status: 'PENDING' | 'PROCESSING' | 'READY' | 'FAILED';
  processing_error: string | null;
  persons: ExtractedPerson[] | null;
  family_groups: ExtractedFamilyGroup[] | null;
  photo_urls: Record<string, string>;
}
