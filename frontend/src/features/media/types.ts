export type MediaCategory = 'PHOTO' | 'DOCUMENT' | 'AUDIO' | 'VIDEO' | 'OTHER';

export type ProcessingStatus =
  | 'PENDING'
  | 'CONFIRMED'
  | 'PROCESSING'
  | 'READY'
  | 'FAILED';

export interface MediaItem {
  media_id: string;
  status: ProcessingStatus;
  category: MediaCategory;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  celery_task_id?: string | null;
  processing_error?: string | null;

  // Variant URLs (present when READY)
  thumb_200_url?: string | null;
  thumb_600_url?: string | null;
  compressed_url?: string | null;
  preview_url?: string | null;

  // Metadata
  title?: string | null;
  description?: string | null;
  date_circa?: string | null;
  year?: number | null;
  tags: string[];
  image_width?: number | null;
  image_height?: number | null;
  duration_seconds?: number | null;
  created_at: string;
}

export interface PresignedTicket {
  media_id: string;
  upload_url: string;
  upload_fields: Record<string, string>;
  storage_key: string;
  expires_in_seconds: number;
  max_size_bytes: number;
}

export interface RequestUploadUrlPayload {
  tree_id: string;
  person_id?: string | null;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
}

export interface UploadProgress {
  mediaId: string;
  filename: string;
  progress: number;   // 0–100
  status: 'uploading' | 'processing' | 'ready' | 'error';
  errorMessage?: string;
  previewUrl?: string;  // local object URL for instant preview
}
