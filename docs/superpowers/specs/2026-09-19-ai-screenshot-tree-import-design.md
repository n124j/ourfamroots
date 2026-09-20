# AI Screenshot → Family Tree Import

Status: Approved (design). Not yet implemented.

## Problem

An admin has a screenshot of a family tree (e.g. a chart found online, or a
photo of a hand-drawn tree) and wants it turned into a real, editable tree in
the app, including cropped photos per person, without manually transcribing
every name and relationship (as was done by hand for the Deol family tree in
this same project — see `Deol_Family.ofr` / `Deol_Family.zip` at the repo
root for a worked example of the target output shape).

## Scope

- Admin-only (global `app_role` of `ADMIN` or `SUPER_ADMIN`), **and** gated to
  paid subscribers (`PREMIUM_INDIVIDUAL` or `PREMIUM_TEAM` tier). Super Admin
  bypasses the paid check entirely, matching the existing precedent in
  `get_my_filters` (`backend/src/api/v1/subscriptions.py:566`) where Super
  Admin is "opted out of the subscription model entirely."
- One screenshot in, one new tree out. No merging into an existing tree in
  this version.
- Extraction includes both structured data (people, sex, unions,
  parent/child links) **and** automatic photo cropping per person, using
  AI-returned bounding boxes.
- Nothing is written to real tree tables until the admin explicitly reviews
  and confirms the extracted draft.
- Out of scope for this version: per-tenant rate/cost caps on the AI calls,
  merging into an existing tree, batch/multi-screenshot import, a confidence
  score UI (the model is instructed to omit uncertain reads rather than
  score them — review is the safety net).

## Access gating

New `AdminPaidFeatureDep` in `backend/src/api/deps.py`, composed from:

1. `AdminUserDep`'s existing check (`app_role in (ADMIN, SUPER_ADMIN)`).
2. If `app_role == SUPER_ADMIN`: allow unconditionally.
3. Otherwise, require an active subscription entitlement, reusing the exact
   query shape from `get_my_filters` (`subscriptions.py:572-587`) but
   filtering on `tier` instead of `filter_key`:

   ```sql
   SELECT 1
   FROM subscriptions s
   WHERE (s.expires_at IS NULL OR s.expires_at > now())
     AND s.tier IN ('PREMIUM_INDIVIDUAL', 'PREMIUM_TEAM')
     AND (
       s.is_default
       OR EXISTS (
         SELECT 1 FROM subscription_members sm
         WHERE sm.subscription_id = s.id AND sm.user_id = :uid
       )
     )
   LIMIT 1
   ```

   No match → `403 Forbidden` ("This feature requires a paid subscription.").

## Data model additions

New table `ai_tree_import_jobs`:

| column | type | notes |
|---|---|---|
| `id` | UUID PK | job id, returned to the client |
| `tenant_id` | UUID | scoping, same convention as other tables |
| `created_by` | UUID FK → users | the admin who started the job |
| `status` | text | `PENDING_UPLOAD` \| `PROCESSING` \| `READY` \| `FAILED` |
| `screenshot_storage_key` | text | S3 key of the uploaded source image |
| `celery_task_id` | text, nullable | for observability, same pattern as `media.celery_task_id` |
| `result_json` | JSONB, nullable | draft `{persons: [...], family_groups: [...]}` once `READY`, in the same shape as the `.ofr` schema, with an added `bbox` field per person |
| `photo_staging_prefix` | text | e.g. `tenants/{tid}/ai-imports/{job_id}/photos/` |
| `processing_error` | text, nullable | populated on `FAILED` |
| `created_at` / `updated_at` | timestamptz | |

Rows (and their staged S3 objects) are deleted after a successful `finalize`,
or left to expire after a short TTL (e.g. 24h) via the existing periodic-task
mechanism already used for subscription expiry reminders
(`src/infrastructure/subscriptions/subscription_tasks.py`) — a follow-up
cleanup task modeled the same way.

## Pipeline

Modeled directly on the existing presigned-upload → confirm → Celery → poll
flow already proven in `backend/src/api/v1/media.py`.

1. **`POST /admin/ai-tree-import/upload-url`** *(AdminPaidFeatureDep)*
   Validates content-type (jpg/png/webp) and size (reuse
   `MediaApplicationService`'s existing limits/validation), creates the job
   row (`status=PENDING_UPLOAD`), returns a presigned S3 POST via the
   existing `_make_s3_client`/presign helpers in `src/api/v1/_s3.py`.

2. Client uploads the screenshot directly to S3 (unchanged from the media
   flow).

3. **`POST /admin/ai-tree-import/{job_id}/confirm`** *(AdminPaidFeatureDep)*
   Verifies the object exists in S3, sets `status=PROCESSING`, dispatches
   `extract_tree_from_screenshot_task.delay(job_id)` — a new Celery task in
   a new `src/infrastructure/ai_import/` module, alongside the existing
   `broadcast_tasks.py` / media task modules.

4. **Celery task** `extract_tree_from_screenshot_task`:
   - Downloads the screenshot from S3.
   - Calls Claude (vision-capable model) via the Anthropic API, using
     **tool use** to force a strict JSON schema:
     `persons[]` (`display_given_name`, `display_surname`, `sex`,
     `bbox: [x, y, w, h]` normalized 0–1, bbox omitted if no photo is
     visible for that person) and `family_groups[]` (`parent_ids`,
     `children: {person_id: parentage_type}`), i.e. the same shape as
     `_OfrPerson`/`_OfrFamilyGroup` in `collaboration.py:1920-1952`, plus
     the bbox. The model is instructed to omit any person/relationship it
     isn't reasonably confident about rather than guess.
   - For each person with a `bbox`, crops the region out of the source
     image with Pillow (same technique used by hand for the Deol tree) and
     uploads the crop to the job's `photo_staging_prefix`.
   - Writes `result_json` (draft persons/family_groups, each photographed
     person's entry carrying its staged S3 key) and sets `status=READY`.
   - On any exception (API error, timeout, schema validation failure):
     sets `status=FAILED` and `processing_error` to a human-readable
     message. Nothing partial is left in real tree tables since none of
     this touches them yet.

5. **`GET /admin/ai-tree-import/{job_id}`** *(AdminPaidFeatureDep)*
   Polling endpoint, same shape as `GET /media/{media_id}`. While
   `PROCESSING`, returns just `status`. Once `READY`, also returns the
   draft `persons`/`family_groups` plus a presigned GET URL per staged
   photo (for thumbnails in the review UI). While `FAILED`, returns
   `processing_error`.

## Review & finalize

**Review UI** (new frontend screen, not the full tree canvas — a bespoke
mini graph-editor for unsaved draft data would duplicate most of the
existing tree editor for little benefit):

- One card per detected person: cropped-photo thumbnail, editable
  given/surname/sex/living fields, a delete button; an "add person" button
  for anyone the AI missed entirely.
- One row per detected family group: two parent dropdowns (populated from
  the person list above) and a children list, each child with a parentage-
  type dropdown; add/remove group controls.
- Same field set as the `.ofr` schema, so this is a thin form wrapper, not a
  new data model.

**`POST /admin/ai-tree-import/{job_id}/finalize`** *(AdminPaidFeatureDep)*,
body = the (possibly hand-edited) `persons[]`/`family_groups[]`:

- Runs the same "create tree from persons + family_groups + photo map"
  logic already in `import_tree_zip` (`collaboration.py:2143+`) — this
  logic should be extracted into a shared helper so both endpoints call it,
  rather than duplicating the tree/person/family-group creation SQL.
- The only difference from the zip-import path: photos are copied from the
  job's *staging* S3 prefix to the permanent photo path, instead of coming
  from an in-memory zip's bytes.
- Returns the new `tree_id`. Frontend redirects into the normal
  `FamilyTreePage` for it — from this point it's an ordinary, fully-editable
  tree, no different from one created any other way.
- On success, the job row and its staged S3 objects are deleted.

## Error handling

- Bad upload (wrong content-type/too large) → rejected at the
  `upload-url` step, reusing `MediaApplicationService`'s existing
  validation and its `HTTPException` mapping (`_handle_media_exception`
  pattern in `media.py:84-93`).
- Vision call failure/timeout/schema-invalid response → job `FAILED` with a
  readable `processing_error`; admin just re-uploads. No cleanup needed
  since nothing is written to real tree tables until `finalize`.
- No per-tenant rate/cost cap in this version (see Scope) — flagged as a
  follow-up if usage warrants it.

## Testing

- `AdminPaidFeatureDep`: free-tier admin blocked, paid non-admin blocked,
  paid admin allowed, super admin allowed regardless of tier — unit tests
  in the style of the existing `test_ofr_import_export.py`.
- Celery task's parsing/validation of the vision model's tool-use output:
  mock the Anthropic client, feed canned JSON (including a case with a
  missing bbox and a case with a schema-invalid response), assert correct
  crop boxes and draft construction / correct `FAILED` handling.
- `finalize`: parameterized like the existing OFR import tests, asserting
  the extracted shared helper produces identical persons/family_groups
  whether invoked from `import_tree_zip` or from this new endpoint.
- Real extraction *accuracy* cannot be unit-tested — needs manual QA against
  a handful of real screenshots (including a busy multi-generation chart
  like the Deol family tree already in this repo) before shipping.
