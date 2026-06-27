/**
 * MediaUploader — drag-and-drop + file-picker with inline progress.
 * Delegates to useMediaUpload for the 3-step S3 flow.
 */
import React, { useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMediaUpload } from '../useMediaUpload';
import type { UploadProgress } from '../types';

// Accepted MIME types (mirrors backend MIME_CATEGORY)
const ACCEPTED = [
  'image/jpeg', 'image/png', 'image/webp', 'image/gif',
  'image/heic', 'image/heif', 'image/tiff',
  'application/pdf',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'audio/mpeg', 'audio/wav', 'audio/ogg',
  'video/mp4', 'video/quicktime', 'video/avi',
].join(',');

interface Props {
  treeId: string;
  personId?: string | null;
  onUploadComplete?: (mediaId: string) => void;
}

export function MediaUploader({ treeId, personId, onUploadComplete }: Props) {
  const { t } = useTranslation();
  const { uploads, uploadFile, clearUpload } = useMediaUpload(treeId, personId);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files) return;
      for (const file of Array.from(files)) {
        try {
          const id = await uploadFile(file);
          onUploadComplete?.(id);
        } catch {
          // error is reflected in uploads state
        }
      }
    },
    [uploadFile, onUploadComplete]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles]
  );

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={[
          'flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed',
          'p-8 cursor-pointer transition-colors select-none',
          dragging
            ? 'border-indigo-500 bg-indigo-50'
            : 'border-gray-300 hover:border-indigo-400 hover:bg-gray-50',
        ].join(' ')}
      >
        <UploadIcon />
        <span className="text-sm font-medium text-gray-700">
          {t('mediaUploader.dropFiles')} <span className="text-indigo-600">{t('mediaUploader.browse')}</span>
        </span>
        <span className="text-xs text-gray-500">
          {t('mediaUploader.sizeHint')}
        </span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          className="sr-only"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* Upload queue */}
      {uploads.length > 0 && (
        <ul className="space-y-2">
          {uploads.map((u) => (
            <UploadRow key={u.mediaId} item={u} onDismiss={() => clearUpload(u.mediaId)} />
          ))}
        </ul>
      )}
    </div>
  );
}

// ── Upload row ─────────────────────────────────────────────────────────────────

function UploadRow({ item, onDismiss }: { item: UploadProgress; onDismiss: () => void }) {
  const isDone    = item.status === 'ready';
  const isError   = item.status === 'error';
  const isActive  = item.status === 'uploading' || item.status === 'processing';

  return (
    <li className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-3">
      {/* Thumbnail or icon */}
      {item.previewUrl ? (
        <img
          src={item.previewUrl}
          alt=""
          className="h-10 w-10 rounded object-cover flex-shrink-0"
        />
      ) : (
        <FileIcon className="h-10 w-10 flex-shrink-0 text-gray-400" />
      )}

      <div className="flex-1 min-w-0">
        <p className="truncate text-sm font-medium text-gray-800">{item.filename}</p>

        {isActive && (
          <div className="mt-1">
            <div className="h-1.5 w-full rounded-full bg-gray-100">
              <div
                className="h-1.5 rounded-full bg-indigo-500 transition-all"
                style={{ width: `${item.status === 'processing' ? 100 : item.progress}%` }}
              />
            </div>
            <p className="mt-0.5 text-xs text-gray-500">
              {item.status === 'processing' ? 'Processing…' : `${item.progress}%`}
            </p>
          </div>
        )}

        {isDone && (
          <p className="mt-0.5 text-xs text-green-600">Ready</p>
        )}

        {isError && (
          <p className="mt-0.5 text-xs text-red-500 truncate">{item.errorMessage}</p>
        )}
      </div>

      {!isActive && (
        <button
          onClick={onDismiss}
          className="flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          aria-label="Dismiss"
        >
          <XIcon />
        </button>
      )}
    </li>
  );
}

// ── Micro icons ────────────────────────────────────────────────────────────────

function UploadIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
    </svg>
  );
}

function FileIcon({ className }: { className?: string }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
