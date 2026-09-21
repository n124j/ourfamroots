import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useAiTreeImportJob } from '@features/admin/aiTreeImport/useAiTreeImportJob';
import { get, post } from '@api/client';

vi.mock('@api/client', () => ({ get: vi.fn(), post: vi.fn() }));

describe('useAiTreeImportJob', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    global.XMLHttpRequest = vi.fn(() => ({
      open: vi.fn(),
      send: vi.fn(function (this: any) {
        this.status = 200;
        this.onload();
      }),
      upload: {},
    })) as any;
  });

  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('walks through uploading -> processing -> ready', async () => {
    (post as any).mockImplementation((url: string) => {
      if (url === '/admin/ai-tree-import/upload-url') {
        return Promise.resolve({
          job_id: 'job-1', upload_url: 'https://s3.example/', upload_fields: {}, max_size_bytes: 1000,
        });
      }
      if (url === '/admin/ai-tree-import/job-1/confirm') {
        return Promise.resolve({ job_id: 'job-1', status: 'PROCESSING' });
      }
      return Promise.reject(new Error(`unexpected post ${url}`));
    });
    (get as any).mockResolvedValue({
      job_id: 'job-1', status: 'READY', processing_error: null,
      persons: [{ id: 'p1', display_given_name: 'A', display_surname: 'B', sex: 'MALE' }],
      family_groups: [], photo_urls: {},
    });

    const { result } = renderHook(() => useAiTreeImportJob());

    await act(async () => {
      await result.current.uploadScreenshot(new File(['x'], 'shot.jpg', { type: 'image/jpeg' }));
    });

    expect(result.current.status).toBe('processing');

    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(result.current.status).toBe('ready');
    expect(result.current.draft?.persons[0].display_given_name).toBe('A');
  });

  it('surfaces a FAILED job as an error', async () => {
    (post as any).mockImplementation((url: string) => {
      if (url === '/admin/ai-tree-import/upload-url') {
        return Promise.resolve({
          job_id: 'job-2', upload_url: 'https://s3.example/', upload_fields: {}, max_size_bytes: 1000,
        });
      }
      if (url === '/admin/ai-tree-import/job-2/confirm') {
        return Promise.resolve({ job_id: 'job-2', status: 'PROCESSING' });
      }
      return Promise.reject(new Error('unexpected'));
    });
    (get as any).mockResolvedValue({
      job_id: 'job-2', status: 'FAILED', processing_error: 'vision call failed',
      persons: null, family_groups: null, photo_urls: {},
    });

    const { result } = renderHook(() => useAiTreeImportJob());
    await act(async () => {
      await result.current.uploadScreenshot(new File(['x'], 'shot.jpg', { type: 'image/jpeg' }));
    });

    expect(result.current.status).toBe('processing');

    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(result.current.status).toBe('error');
    expect(result.current.errorMessage).toBe('vision call failed');
  });
});
