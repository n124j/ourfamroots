# Media Management Architecture

## Upload Pipeline

```
┌─────────┐  1. POST /media/upload-url      ┌──────────┐
│ Browser │ ─────────────────────────────►  │ FastAPI  │
│         │  ← { media_id, presigned_url }  │          │
│         │                                 │ creates  │
│         │  2. PUT <presigned_url> (file)  │ MediaItem│
│         │ ─────────────────────────────►  │ PENDING  │
│         │    (direct to S3, no backend)   └──────────┘
│         │                                      │
│         │  3. POST /media/{id}/confirm          │
│         │ ─────────────────────────────►        │
│         │  ← { status: "processing" }     enqueues Celery task
└─────────┘                                       │
                                                  ▼
                                         ┌────────────────┐
                                         │  Redis broker  │
                                         └───────┬────────┘
                                                 │
                                    ┌────────────▼────────────┐
                                    │      Celery Worker      │
                                    │                         │
                                    │  download_from_s3()     │
                                    │       ↓                 │
                                    │  extract_metadata()     │  ← EXIF, GPS, PDF text
                                    │       ↓                 │
                                    │  generate_thumbnails()  │  ← 200px, 600px WebP
                                    │       ↓                 │
                                    │  compress_original()    │  ← WebP @ 85% quality
                                    │       ↓                 │
                                    │  upload_variants_s3()   │
                                    │       ↓                 │
                                    │  update_db(READY)       │
                                    └─────────────────────────┘
                                                 │
                                    ┌────────────▼────────────┐
                                    │ 4. Frontend polls       │
                                    │  GET /media/{id}        │
                                    │  until status = READY   │
                                    └─────────────────────────┘
```

## S3 Key Structure

```
{tenant_id}/
  {tree_id}/
    {person_id}/          ← media attached to a person
      {media_id}/
        original.{ext}    ← untouched original
        compressed.webp   ← images: WebP @ 85 quality
        thumb_200.webp    ← square 200×200 crop
        thumb_600.webp    ← max 600px (longest edge)
        preview.jpg       ← PDFs: first-page render
        metadata.json     ← extracted EXIF / PDF text (cached)

  trees/
    {tree_id}/            ← media attached to the tree itself (cover photo etc.)
      {media_id}/
        ...

  users/
    {user_id}/
      avatar/
        {uuid}.{ext}      ← user profile picture (local users only)
```

### User Avatar Upload (separate from media pipeline)

User profile pictures bypass the Celery media pipeline. They are uploaded
server-side via `POST /api/v1/users/me/avatar` (multipart form) and stored
directly in S3 without thumbnail generation. The original image is served
via presigned URL. OAuth users (Google, GitHub) have their avatar synced from
the provider and cannot upload manually (returns 403).

## Supported Media Types

| Category  | MIME types                          | Processing                         |
|-----------|-------------------------------------|------------------------------------|
| Photo     | image/jpeg, image/png, image/webp   | Thumbnails + compression + EXIF    |
| Raw photo | image/heic, image/heif              | Convert → JPEG, then as above      |
| GIF       | image/gif                           | Thumbnails only (no compress)      |
| Document  | application/pdf                     | Text extract + first-page preview  |
| Doc       | application/msword, .docx           | Text extract only                  |
| Audio     | audio/mpeg, audio/wav               | Duration extract only              |
| Video     | video/mp4                           | Thumbnail @ 1s + duration          |

## Size Limits

| Tier       | Max file size | Rationale                    |
|------------|---------------|------------------------------|
| Image      | 50 MB         | RAW photos                   |
| Document   | 100 MB        | Large scanned documents      |
| Audio      | 200 MB        | Long recordings              |
| Video      | 500 MB        | Home videos                  |

## Redis Usage

| Key pattern                          | Purpose                          | TTL     |
|--------------------------------------|----------------------------------|---------|
| `media:status:{media_id}`            | Celery task status cache         | 1 hour  |
| `media:gallery:{tree_id}:{person_id}`| Gallery page cache               | 5 min   |
| `media:presign:{media_id}`           | Presigned URL dedup              | 55 min  |

## Celery Task Graph

```python
chord(
    group(
        extract_metadata.s(media_id),    # parallel
        generate_thumbnails.s(media_id), # parallel
    ),
    finalize_media.s(media_id)           # runs after both complete
)
```

## Worker Configuration

- Queue: `media` (separate from default queue)
- Concurrency: 4 workers per node (I/O-bound — downloading/uploading S3)
- Max tasks per child: 50 (prevents Pillow memory leaks)
- Soft time limit: 120s per task; hard limit: 180s
- Retry: 3 attempts with exponential back-off (30s, 90s, 270s)
