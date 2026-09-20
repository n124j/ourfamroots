/**
 * useAiTreeImportJob — drives one admin AI-screenshot-import job:
 *   1. POST /admin/ai-tree-import/upload-url  → presigned POST ticket
 *   2. POST <presigned_url>                   → direct S3 upload
 *   3. POST /admin/ai-tree-import/{id}/confirm → triggers Celery extraction
 * Then polls GET /admin/ai-tree-import/{id} until READY or FAILED.
 */
import { useCallback, useRef, useState } from 'react';
import { post } from '@api/client';
import type { ExtractedDraft, JobStatusResponse, UploadUrlResponse } from './types';

const POLL_INTERVAL_MS = 2_000;
const POLL_TIMEOUT_MS = 3 * 60 * 1_000; // 3 minutes

export type AiImportStatus = 'idle' | 'uploading' | 'processing' | 'ready' | 'error';

export function useAiTreeImportJob() {
  const [status, setStatus] = useState<AiImportStatus>('idle');
  const [jobId, setJobId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ExtractedDraft | null>(null);
  const [photoUrls, setPhotoUrls] = useState<Record<string, string>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  const xhrUpload = useCallback((ticket: UploadUrlResponse, file: File): Promise<void> =>
    new Promise((resolve, reject) => {
      const form = new FormData();
      Object.entries(ticket.upload_fields).forEach(([k, v]) => form.append(k, v));
      form.append('file', file);

      const xhr = new XMLHttpRequest();
      xhr.open('POST', ticket.upload_url);
      xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`S3 upload failed: HTTP ${xhr.status}`)));
      xhr.onerror = () => reject(new Error('S3 upload network error'));
      xhr.send(form);
    }), []);

  const pollUntilDone = useCallback((id: string) => {
    const started = Date.now();
    pollTimer.current = setInterval(async () => {
      if (Date.now() - started > POLL_TIMEOUT_MS) {
        stopPolling();
        setStatus('error');
        setErrorMessage('Extraction timed out.');
        return;
      }
      try {
        const res = await fetch(`/api/v1/admin/ai-tree-import/${id}`, { credentials: 'include' });
        const job: JobStatusResponse = await res.json();
        if (job.status === 'READY') {
          stopPolling();
          setDraft({ persons: job.persons ?? [], family_groups: job.family_groups ?? [] });
          setPhotoUrls(job.photo_urls);
          setStatus('ready');
        } else if (job.status === 'FAILED') {
          stopPolling();
          setErrorMessage(job.processing_error ?? 'Extraction failed.');
          setStatus('error');
        }
      } catch {
        // transient network error — keep polling
      }
    }, POLL_INTERVAL_MS);
  }, [stopPolling]);

  const uploadScreenshot = useCallback(async (file: File): Promise<void> => {
    setStatus('uploading');
    setErrorMessage(null);
    try {
      const ticket = await post<UploadUrlResponse>('/admin/ai-tree-import/upload-url', {
        content_type: file.type,
        file_size_bytes: file.size,
      });
      setJobId(ticket.job_id);
      await xhrUpload(ticket, file);
      await post(`/admin/ai-tree-import/${ticket.job_id}/confirm`);
      setStatus('processing');
      pollUntilDone(ticket.job_id);
    } catch (err) {
      setStatus('error');
      setErrorMessage(err instanceof Error ? err.message : 'Upload failed.');
    }
  }, [xhrUpload, pollUntilDone]);

  const reset = useCallback(() => {
    stopPolling();
    setStatus('idle');
    setJobId(null);
    setDraft(null);
    setPhotoUrls({});
    setErrorMessage(null);
  }, [stopPolling]);

  return { status, jobId, draft, photoUrls, errorMessage, uploadScreenshot, reset };
}
