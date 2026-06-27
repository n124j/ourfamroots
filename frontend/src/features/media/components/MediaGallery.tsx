/**
 * MediaGallery — masonry grid of media items with a lightbox overlay.
 * Fetches from GET /trees/{treeId}/persons/{personId}/media via React Query.
 */
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { get } from '@api/client';
import type { MediaItem } from '../types';

interface Props {
  treeId: string;
  personId: string;
}

interface MediaListResponse {
  items: MediaItem[];
  total: number;
}

const mediaKeys = {
  personGallery: (treeId: string, personId: string) =>
    ['media', 'person', treeId, personId] as const,
};

export function MediaGallery({ treeId, personId }: Props) {
  const [lightboxId, setLightboxId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: mediaKeys.personGallery(treeId, personId),
    queryFn: () =>
      get<MediaListResponse>(`/trees/${treeId}/persons/${personId}/media`),
    staleTime: 30_000,
  });

  if (isLoading) return <GallerySkeleton />;
  if (isError)   return <p className="text-sm text-red-500">Failed to load media.</p>;
  if (!data?.items.length) return <EmptyState />;

  const lightboxItem = lightboxId
    ? data.items.find((m) => m.media_id === lightboxId) ?? null
    : null;

  return (
    <>
      {/* Masonry grid (CSS columns) */}
      <div className="columns-2 gap-2 sm:columns-3 lg:columns-4">
        {data.items.map((item) => (
          <GalleryCard
            key={item.media_id}
            item={item}
            onClick={() => setLightboxId(item.media_id)}
          />
        ))}
      </div>

      {/* Lightbox */}
      {lightboxItem && (
        <Lightbox item={lightboxItem} onClose={() => setLightboxId(null)} />
      )}
    </>
  );
}

// ── Gallery card ───────────────────────────────────────────────────────────────

function GalleryCard({ item, onClick }: { item: MediaItem; onClick: () => void }) {
  const thumb = item.thumb_200_url ?? item.preview_url;
  const ready = item.status === 'READY';

  return (
    <div
      className="mb-2 break-inside-avoid cursor-pointer overflow-hidden rounded-lg bg-gray-100 shadow-sm hover:shadow-md transition-shadow"
      onClick={onClick}
    >
      {thumb && ready ? (
        <img
          src={thumb}
          alt={item.title ?? item.original_filename}
          className="w-full object-cover"
          loading="lazy"
        />
      ) : (
        <PlaceholderTile item={item} />
      )}
      {(item.title || item.year) && (
        <div className="px-2 py-1.5">
          {item.title && (
            <p className="truncate text-xs font-medium text-gray-800">{item.title}</p>
          )}
          {item.year && (
            <p className="text-xs text-gray-500">{item.year}</p>
          )}
        </div>
      )}
    </div>
  );
}

function PlaceholderTile({ item }: { item: MediaItem }) {
  const icon = CATEGORY_ICON[item.category] ?? '📎';
  const processing = item.status === 'PROCESSING' || item.status === 'CONFIRMED';

  return (
    <div className="flex h-24 items-center justify-center gap-2 text-gray-400">
      <span className="text-2xl">{icon}</span>
      {processing && (
        <span className="text-xs">Processing…</span>
      )}
    </div>
  );
}

const CATEGORY_ICON: Record<string, string> = {
  PHOTO: '🖼',
  DOCUMENT: '📄',
  AUDIO: '🎵',
  VIDEO: '🎬',
  OTHER: '📎',
};

// ── Lightbox ───────────────────────────────────────────────────────────────────

function Lightbox({ item, onClose }: { item: MediaItem; onClose: () => void }) {
  const displayUrl = item.compressed_url ?? item.thumb_600_url ?? item.thumb_200_url;
  const isPhoto    = item.category === 'PHOTO';
  const isPdf      = item.content_type === 'application/pdf';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4"
      onClick={onClose}
    >
      <div
        className="relative max-h-[90vh] max-w-4xl overflow-hidden rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute right-3 top-3 z-10 rounded-full bg-black/40 p-1 text-white hover:bg-black/60"
          aria-label="Close"
        >
          <XIcon />
        </button>

        {/* Media area */}
        {isPhoto && displayUrl && (
          <img
            src={displayUrl}
            alt={item.title ?? item.original_filename}
            className="max-h-[70vh] w-full object-contain"
          />
        )}

        {isPdf && (
          <DocumentViewer item={item} />
        )}

        {!isPhoto && !isPdf && (
          <div className="flex h-48 items-center justify-center text-gray-500">
            <span className="text-4xl">{CATEGORY_ICON[item.category]}</span>
          </div>
        )}

        {/* Caption */}
        <div className="px-4 py-3">
          <p className="font-medium text-gray-900">
            {item.title ?? item.original_filename}
          </p>
          {item.description && (
            <p className="mt-1 text-sm text-gray-600">{item.description}</p>
          )}
          <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
            {item.date_circa && <span>📅 {item.date_circa}</span>}
            {item.year && !item.date_circa && <span>📅 {item.year}</span>}
            {item.image_width && item.image_height && (
              <span>🔲 {item.image_width}×{item.image_height}</span>
            )}
            {item.tags.map((t) => (
              <span key={t} className="rounded-full bg-gray-100 px-2 py-0.5">{t}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Document viewer (PDF embed) ────────────────────────────────────────────────

function DocumentViewer({ item }: { item: MediaItem }) {
  const [url, setUrl] = React.useState<string | null>(item.preview_url ?? null);

  // Fetch full download URL on demand
  React.useEffect(() => {
    if (item.status !== 'READY') return;
    fetch(`/api/v1/media/${item.media_id}/download?variant=original`, {
      credentials: 'include',
    })
      .then((r) => r.json())
      .then((d: { url: string }) => setUrl(d.url))
      .catch(() => { /* keep preview */ });
  }, [item.media_id, item.status]);

  if (!url) {
    return (
      <div className="flex h-48 items-center justify-center text-gray-400">
        <span className="text-sm">Loading document…</span>
      </div>
    );
  }

  return (
    <iframe
      src={url}
      title={item.title ?? item.original_filename}
      className="h-[60vh] w-full border-0"
    />
  );
}

// ── Skeleton / empty ───────────────────────────────────────────────────────────

function GallerySkeleton() {
  return (
    <div className="columns-2 gap-2 sm:columns-3 lg:columns-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div
          key={i}
          className="mb-2 break-inside-avoid h-28 animate-pulse rounded-lg bg-gray-200"
        />
      ))}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-gray-400">
      <span className="text-4xl">🖼</span>
      <p className="text-sm">No media yet. Upload photos and documents above.</p>
    </div>
  );
}

function XIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
