/**
 * useMediaUpload — manages the 3-step direct-to-S3 upload flow:
 *   1. POST /media/upload-url  → presigned POST ticket
 *   2. POST <presigned_url>    → direct S3 upload with progress events
 *   3. POST /media/{id}/confirm → triggers Celery processing
 *
 * After confirmation, polls GET /media/{id} until status is READY or FAILED.
 */
import { useCallback, useRef, useState } from 'react';
import { post } from '@api/client';
import type {
  MediaItem,
  PresignedTicket,
  RequestUploadUrlPayload,
  UploadProgress,
} from './types';

const POLL_INTERVAL_MS  = 2_000;
const POLL_TIMEOUT_MS   = 5 * 60 * 1_000; // 5 minutes

export function useMediaUpload(treeId: string, personId?: string | null) {
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  // ── Helpers ────────────────────────────────────────────────────────────────

  const setProgress = useCallback(
    (mediaId: string, patch: Partial<UploadProgress>) =>
      setUploads((prev) =>
        prev.map((u) => (u.mediaId === mediaId ? { ...u, ...patch } : u))
      ),
    []
  );

  const stopPolling = useCallback((mediaId: string) => {
    const timer = pollTimers.current.get(mediaId);
    if (timer) {
      clearInterval(timer);
      pollTimers.current.delete(mediaId);
    }
  }, []);

  // ── Step 2: XHR upload with progress ──────────────────────────────────────

  const xhrUpload = useCallback(
    (ticket: PresignedTicket, file: File): Promise<void> =>
      new Promise((resolve, reject) => {
        const form = new FormData();
        Object.entries(ticket.upload_fields).forEach(([k, v]) => form.append(k, v));
        form.append('file', file);  // "file" must be last field per AWS requirement

        const xhr = new XMLHttpRequest();
        xhr.open('POST', ticket.upload_url);

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            setProgress(ticket.media_id, { progress: pct });
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`S3 upload failed: HTTP ${xhr.status}`));
          }
        };
        xhr.onerror = () => reject(new Error('S3 upload network error'));
        xhr.send(form);
      }),
    [setProgress]
  );

  // ── Step 3 + polling ────────────────────────────────────────────────────────

  const confirmAndPoll = useCallback(
    async (mediaId: string): Promise<void> => {
      await post<MediaItem>(`/media/${mediaId}/confirm`);
      setProgress(mediaId, { status: 'processing', progress: 100 });

      const started = Date.now();
      const timer = setInterval(async () => {
        if (Date.now() - started > POLL_TIMEOUT_MS) {
          stopPolling(mediaId);
          setProgress(mediaId, {
            status: 'error',
            errorMessage: 'Processing timed out.',
          });
          return;
        }

        try {
          const item = await fetch(`/api/v1/media/${mediaId}`, {
            credentials: 'include',
          }).then((r) => r.json() as Promise<MediaItem>);

          if (item.status === 'READY') {
            stopPolling(mediaId);
            setProgress(mediaId, {
              status: 'ready',
              previewUrl: item.thumb_200_url ?? item.preview_url ?? undefined,
            });
          } else if (item.status === 'FAILED') {
            stopPolling(mediaId);
            setProgress(mediaId, {
              status: 'error',
              errorMessage: item.processing_error ?? 'Processing failed.',
            });
          }
        } catch {
          // transient network error — keep polling
        }
      }, POLL_INTERVAL_MS);

      pollTimers.current.set(mediaId, timer);
    },
    [setProgress, stopPolling]
  );

  // ── Public: upload one file ────────────────────────────────────────────────

  const uploadFile = useCallback(
    async (file: File): Promise<string> => {
      // Instant local preview for images
      const localPreview = file.type.startsWith('image/')
        ? URL.createObjectURL(file)
        : undefined;

      // Temporary placeholder ID until we get the real media_id
      const placeholder: UploadProgress = {
        mediaId: `pending-${Date.now()}`,
        filename: file.name,
        progress: 0,
        status: 'uploading',
        previewUrl: localPreview,
      };
      setUploads((prev) => [...prev, placeholder]);

      try {
        // Step 1: request presigned ticket
        const payload: RequestUploadUrlPayload = {
          tree_id: treeId,
          person_id: personId,
          original_filename: file.name,
          content_type: file.type,
          file_size_bytes: file.size,
        };
        const ticket = await post<PresignedTicket>('/media/upload-url', payload);

        // Replace placeholder with real media_id
        setUploads((prev) =>
          prev.map((u) =>
            u.mediaId === placeholder.mediaId
              ? { ...u, mediaId: ticket.media_id }
              : u
          )
        );

        // Step 2: direct S3 upload
        await xhrUpload(ticket, file);

        // Step 3: confirm + poll
        await confirmAndPoll(ticket.media_id);

        return ticket.media_id;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Upload failed.';
        setUploads((prev) =>
          prev.map((u) =>
            u.mediaId === placeholder.mediaId
              ? { ...u, status: 'error', errorMessage: msg }
              : u
          )
        );
        throw err;
      }
    },
    [treeId, personId, xhrUpload, confirmAndPoll]
  );

  const clearUpload = useCallback((mediaId: string) => {
    stopPolling(mediaId);
    setUploads((prev) => prev.filter((u) => u.mediaId !== mediaId));
  }, [stopPolling]);

  return { uploads, uploadFile, clearUpload };
}
