"""API v1 root router — aggregates all sub-routers."""

from fastapi import APIRouter

from src.api.v1.activity import router as activity_router
from src.api.v1.admin import router as admin_router
from src.api.v1.broadcast import router as broadcast_router
from src.api.v1.auth import router as auth_router
from src.api.v1.collaboration import router as collaboration_router
from src.api.v1.contact import router as contact_router
from src.api.v1.discovery import router as discovery_router
from src.api.v1.media import router as media_router
from src.api.v1.notifications import router as notifications_router
from src.api.v1.push import router as push_router
from src.api.v1.oauth import router as oauth_router
from src.api.v1.permission_groups import router as permission_groups_router
from src.api.v1.persons import router as persons_router
from src.api.v1.search import router as search_router
from src.api.v1.site_settings import router as site_settings_router
from src.api.v1.users import router as users_router

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(auth_router)
v1_router.include_router(oauth_router)
v1_router.include_router(contact_router)
v1_router.include_router(users_router)
v1_router.include_router(persons_router)
v1_router.include_router(collaboration_router)
v1_router.include_router(discovery_router)
v1_router.include_router(media_router)
v1_router.include_router(search_router)
v1_router.include_router(activity_router)
v1_router.include_router(admin_router)
v1_router.include_router(permission_groups_router)
v1_router.include_router(notifications_router)
v1_router.include_router(push_router)
v1_router.include_router(site_settings_router)
v1_router.include_router(broadcast_router)
