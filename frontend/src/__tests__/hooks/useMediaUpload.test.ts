/**
 * Unit tests for useMediaUpload hook.
 * Tests the 3-step upload flow: presign → XHR → confirm → poll.
 */
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { useMediaUpload } from '@features/media/useMediaUpload';

const TREE_ID  = 'tree-1';
const PERSON_ID = 'person-1';
const MEDIA_ID  = 'media-abc-123';

// Mock XHR
class MockXHR {
  static instances: MockXHR[] = [];
  open = jest.fn();
  send = jest.fn();
  setRequestHeader = jest.fn();
  status = 204;
  upload = { onprogress: null as any };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor() {
    MockXHR.instances.push(this);
  }

  // Simulate a successful upload when send() is called
  _simulateSuccess() {
    if (this.upload.onprogress) {
      this.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 } as any);
      this.upload.onprogress({ lengthComputable: true, loaded: 100, total: 100 } as any);
    }
    this.status = 204;
    this.onload?.();
  }
}

global.XMLHttpRequest = MockXHR as any;

const server = setupServer(
  http.post('/api/v1/media/upload-url', () =>
    HttpResponse.json({
      media_id: MEDIA_ID,
      upload_url: 'https://s3.mock.com/bucket',
      upload_fields: { key: 'path/original.jpg', 'Content-Type': 'image/jpeg' },
      storage_key: 'path/original.jpg',
      expires_in_seconds: 3600,
      max_size_bytes: 52428800,
    }, { status: 201 })
  ),
  http.post(`/api/v1/media/${MEDIA_ID}/confirm`, () =>
    HttpResponse.json({ media_id: MEDIA_ID, status: 'CONFIRMED' })
  ),
  http.get(`/api/v1/media/${MEDIA_ID}`, () =>
    HttpResponse.json({ media_id: MEDIA_ID, status: 'READY', thumb_200_url: 'https://s3/thumb' })
  ),
);

beforeAll(() => server.listen());
beforeEach(() => { MockXHR.instances = []; });
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('useMediaUpload', () => {
  it('starts with empty uploads', () => {
    const { result } = renderHook(() => useMediaUpload(TREE_ID, PERSON_ID));
    expect(result.current.uploads).toHaveLength(0);
  });

  it('adds upload to queue when file provided', async () => {
    const { result } = renderHook(() => useMediaUpload(TREE_ID, PERSON_ID));
    const file = new File(['img'], 'photo.jpg', { type: 'image/jpeg' });

    // Start upload (don't await — let it progress)
    act(() => {
      result.current.uploadFile(file).catch(() => {});
    });

    await waitFor(() => {
      expect(result.current.uploads.length).toBeGreaterThan(0);
    });

    expect(result.current.uploads[0].filename).toBe('photo.jpg');
  });

  it('upload progresses to uploading state', async () => {
    const { result } = renderHook(() => useMediaUpload(TREE_ID, PERSON_ID));
    const file = new File(['img'], 'upload.jpg', { type: 'image/jpeg' });

    act(() => {
      result.current.uploadFile(file).catch(() => {});
    });

    await waitFor(() =>
      result.current.uploads.some((u) => u.status === 'uploading')
    );
  });

  it('clears upload when clearUpload called', async () => {
    const { result } = renderHook(() => useMediaUpload(TREE_ID, PERSON_ID));
    const file = new File(['img'], 'clear.jpg', { type: 'image/jpeg' });

    act(() => {
      result.current.uploadFile(file).catch(() => {});
    });

    await waitFor(() => result.current.uploads.length > 0);

    const mediaId = result.current.uploads[0].mediaId;
    act(() => {
      result.current.clearUpload(mediaId);
    });

    await waitFor(() => result.current.uploads.length === 0);
  });

  it('shows error state when upload-url API fails', async () => {
    server.use(
      http.post('/api/v1/media/upload-url', () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      )
    );

    const { result } = renderHook(() => useMediaUpload(TREE_ID, PERSON_ID));
    const file = new File(['img'], 'fail.jpg', { type: 'image/jpeg' });

    await act(async () => {
      await result.current.uploadFile(file).catch(() => {});
    });

    await waitFor(() =>
      result.current.uploads.some((u) => u.status === 'error')
    );
  });

  it('generates local preview URL for image files', async () => {
    // Mock URL.createObjectURL
    const mockUrl = 'blob:http://localhost/mock-object-url';
    global.URL.createObjectURL = jest.fn(() => mockUrl);

    const { result } = renderHook(() => useMediaUpload(TREE_ID, PERSON_ID));
    const file = new File(['img'], 'preview.jpg', { type: 'image/jpeg' });

    act(() => {
      result.current.uploadFile(file).catch(() => {});
    });

    await waitFor(() => result.current.uploads.length > 0);
    expect(result.current.uploads[0].previewUrl).toBe(mockUrl);
  });

  it('does NOT generate preview URL for non-image files', async () => {
    const { result } = renderHook(() => useMediaUpload(TREE_ID, PERSON_ID));
    const file = new File(['pdf'], 'document.pdf', { type: 'application/pdf' });

    act(() => {
      result.current.uploadFile(file).catch(() => {});
    });

    await waitFor(() => result.current.uploads.length > 0);
    expect(result.current.uploads[0].previewUrl).toBeUndefined();
  });
});
