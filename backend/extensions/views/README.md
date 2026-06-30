# Backend View Extensions

This directory is reserved for backend-side view extension logic.

Most view extensions are frontend-only (see `frontend/src/extensions/views/`).
Backend extensions go here when a view needs server-side support such as:

- Custom API endpoints for a specific view's data format
- Server-side rendering or export for a view
- Data aggregation queries specific to a view

## Structure

```
backend/extensions/views/
  <view-name>/
    __init__.py       # Extension metadata
    router.py         # FastAPI router (auto-mounted if present)
    service.py        # Business logic
```

## Currently no backend extensions are needed

The Heritage and Timeline views are purely frontend.
