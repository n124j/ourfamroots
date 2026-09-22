"""Server-rendered HTML for static marketing/acquisition pages, for search
and social-preview crawlers that don't execute the SPA's JavaScript.

Same rationale and nginx bot-detection pattern as
`collaboration.get_shared_tree_og_preview` — see that function's docstring —
but for content that isn't tied to any one tree, so there's no DB lookup:
just a fixed title/description/OG block per page plus a short content
snippet, kept in sync by hand with the matching React page's copy.
"""
from __future__ import annotations

from fastapi import APIRouter, Response

from src.config import get_settings

router = APIRouter(prefix="/marketing", tags=["marketing"])


def _page(path: str, title: str, description: str, heading: str, body: str) -> Response:
    settings = get_settings()
    base_url = settings.frontend_base_url.rstrip("/")
    url = f"{base_url}{path}"
    og_image = f"{base_url}/og-image.svg"

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} | OurFamRoots</title>
<meta name="description" content="{description}">
<link rel="canonical" href="{url}">
<meta property="og:site_name" content="OurFamRoots">
<meta property="og:type" content="website">
<meta property="og:title" content="{title} | OurFamRoots">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title} | OurFamRoots">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{og_image}">
</head>
<body>
<h1>{heading}</h1>
<p>{body}</p>
<p><a href="{base_url}/register">Start building your family tree free</a></p>
</body>
</html>"""
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get(
    "/family-tree-maker",
    summary="Server-rendered HTML for the /family-tree-maker marketing page (crawlers only)",
    response_class=Response,
)
async def family_tree_maker_preview() -> Response:
    return _page(
        path="/family-tree-maker",
        title="Free Family Tree Maker",
        description=(
            "Build a collaborative family tree online for free. Multiple layouts — "
            "generation, pedigree, ancestor, descendant, and fan chart — with role-based "
            "collaboration so relatives can help fill it in together."
        ),
        heading="Free Family Tree Maker",
        body=(
            "OurFamRoots is a free, collaborative family tree builder. Add relatives, "
            "attach photos, and switch between generation, pedigree, ancestor/descendant, "
            "and fan chart layouts — then invite family members to help build it with you."
        ),
    )


@router.get(
    "/fan-chart-generator",
    summary="Server-rendered HTML for the /fan-chart-generator marketing page (crawlers only)",
    response_class=Response,
)
async def fan_chart_generator_preview() -> Response:
    return _page(
        path="/fan-chart-generator",
        title="Free Fan Chart Generator",
        description=(
            "Generate a printable ancestor fan chart from your family tree for free — "
            "a circular, multi-ring view of your ancestors, built and updated automatically "
            "as you add family members."
        ),
        heading="Free Fan Chart Generator",
        body=(
            "Turn your family tree into a circular ancestor fan chart automatically — no "
            "manual layout work. Add ancestors to your OurFamRoots tree and the fan chart "
            "updates itself, ready to share or export."
        ),
    )
