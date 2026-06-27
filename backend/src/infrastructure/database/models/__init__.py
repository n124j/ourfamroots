"""ORM model package — import all models here so Alembic autogenerate sees them."""

from src.infrastructure.database.models.tenant import TenantModel
from src.infrastructure.database.models.user import UserModel, UserOAuthProviderModel
from src.infrastructure.database.models.login_event import LoginEventModel
from src.infrastructure.database.models.collaboration import (
    FamilyTreeModel,
    TreeMemberModel,
    TreePinModel,
)
from src.infrastructure.database.models.person import (
    PersonModel,
    FamilyGroupModel,
    FamilyGroupMemberModel,
)
from src.infrastructure.database.models.permission_group import (
    PermissionGroupModel,
    PermissionGroupAssignmentModel,
    PermissionGroupTreeModel,
    PermissionGroupMemberModel,
)
from src.infrastructure.database.models.site_settings import SiteSettingsModel
from src.infrastructure.database.models.broadcast_log import BroadcastLogModel

__all__ = [
    "TenantModel",
    "UserModel",
    "UserOAuthProviderModel",
    "LoginEventModel",
    "FamilyTreeModel",
    "TreeMemberModel",
    "TreePinModel",
    "PersonModel",
    "FamilyGroupModel",
    "FamilyGroupMemberModel",
    "PermissionGroupModel",
    "PermissionGroupAssignmentModel",
    "PermissionGroupTreeModel",
    "PermissionGroupMemberModel",
    "SiteSettingsModel",
    "BroadcastLogModel",
]
