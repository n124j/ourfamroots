/**
 * MediaPanel — combined uploader + gallery panel for a person profile.
 * Drop this into any person detail page/drawer.
 */
import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { MediaUploader } from './MediaUploader';
import { MediaGallery } from './MediaGallery';

interface Props {
  treeId: string;
  personId: string;
}

export function MediaPanel({ treeId, personId }: Props) {
  const qc = useQueryClient();

  const handleUploadComplete = () => {
    // Invalidate gallery so new item appears immediately
    qc.invalidateQueries({
      queryKey: ['media', 'person', treeId, personId],
    });
  };

  return (
    <div className="space-y-4">
      <MediaUploader
        treeId={treeId}
        personId={personId}
        onUploadComplete={handleUploadComplete}
      />
      <MediaGallery treeId={treeId} personId={personId} />
    </div>
  );
}
