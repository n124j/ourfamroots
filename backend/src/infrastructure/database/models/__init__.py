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
from src.infrastructure.database.models.namespace_invitation import NamespaceInvitationModel
from src.infrastructure.database.models.user_group import (
    UserGroupModel,
    UserGroupMemberModel,
    PermissionGroupUserGroupModel,
)
from src.infrastructure.database.models.site_settings import SiteSettingsModel
from src.infrastructure.database.models.broadcast_log import BroadcastLogModel
from src.infrastructure.database.models.subscription import (
    SubscriptionModel,
    SubscriptionFilterModel,
    SubscriptionMemberModel,
)

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
    "NamespaceInvitationModel",
    "UserGroupModel",
    "UserGroupMemberModel",
    "PermissionGroupUserGroupModel",
    "SiteSettingsModel",
    "BroadcastLogModel",
    "SubscriptionModel",
    "SubscriptionFilterModel",
    "SubscriptionMemberModel",
]
