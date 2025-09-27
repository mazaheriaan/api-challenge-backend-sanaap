from typing import Dict, Iterable, List, Optional, Set, Union

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db.models import Q, QuerySet
from guardian.core import ObjectPermissionChecker
from guardian.shortcuts import (
    assign_perm,
    get_objects_for_user,
    get_users_with_perms,
    remove_perm,
)

from sanaap_api_challenge.documents.models import Document, Share

User = get_user_model()


class CachedPermissionChecker:
    CACHE_PREFIX = "doc_perms"
    CACHE_TIMEOUT = 300  # 5 minutes

    def __init__(self, user_or_group: Union[User, Group]):
        self.user_or_group = user_or_group
        self.checker = ObjectPermissionChecker(user_or_group)
        self.is_user = isinstance(user_or_group, User)
        self._cache_key_prefix = self._get_cache_key_prefix()

    def _get_cache_key_prefix(self) -> str:
        obj_type = "user" if self.is_user else "group"
        obj_id = self.user_or_group.id
        return f"{self.CACHE_PREFIX}:{obj_type}:{obj_id}"

    def _get_cache_key(self, permission: str, obj: Document) -> str:
        return f"{self._cache_key_prefix}:{permission}:{obj.id}"

    def has_perm(self, permission: str, obj: Document) -> bool:
        cache_key = self._get_cache_key(permission, obj)
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        result = self.checker.has_perm(permission, obj)

        cache.set(cache_key, result, self.CACHE_TIMEOUT)

        return result

    def prefetch_perms(self, objects: Iterable[Document]) -> None:
        """
        Prefetch permissions for multiple objects to optimize queries.

        This should be called before looping through objects to check permissions.
        """
        self.checker.prefetch_perms(objects)

        for obj in objects:
            for perm in self.checker.get_perms(obj):
                cache_key = self._get_cache_key(perm, obj)
                cache.set(cache_key, True, self.CACHE_TIMEOUT)

    def get_perms(self, obj: Document) -> List[str]:
        cache_key = f"{self._cache_key_prefix}:all_perms:{obj.id}"
        cached_perms = cache.get(cache_key)

        if cached_perms is not None:
            return cached_perms

        perms = self.checker.get_perms(obj)
        cache.set(cache_key, perms, self.CACHE_TIMEOUT)

        return perms

    def invalidate_cache(self, obj: Optional[Document] = None) -> None:
        if obj:
            pattern = f"{self._cache_key_prefix}:*:{obj.id}"
        else:
            pattern = f"{self._cache_key_prefix}:*"

        cache.delete_pattern(pattern)


class BulkPermissionManager:
    @staticmethod
    def assign_bulk_permissions(
        permissions: List[str],
        users: List[User],
        obj: Document,
    ) -> int:
        count = 0
        for user in users:
            for perm in permissions:
                assign_perm(perm, user, obj)
                count += 1

        for user in users:
            checker = CachedPermissionChecker(user)
            checker.invalidate_cache(obj)

        return count

    @staticmethod
    def remove_bulk_permissions(
        permissions: List[str],
        users: List[User],
        obj: Document,
    ) -> int:
        count = 0
        for user in users:
            for perm in permissions:
                remove_perm(perm, user, obj)
                count += 1

        # Invalidate cache for all affected users
        for user in users:
            checker = CachedPermissionChecker(user)
            checker.invalidate_cache(obj)

        return count

    @staticmethod
    def copy_permissions(
        source_doc: Document,
        target_doc: Document,
        include_shares: bool = True,
    ) -> Dict[str, int]:
        result = {"permissions": 0, "shares": 0}

        users_with_perms = get_users_with_perms(
            source_doc,
            attach_perms=True,
            with_group_users=False,
        )

        for user, perms in users_with_perms.items():
            for perm in perms:
                assign_perm(perm, user, target_doc)
                result["permissions"] += 1

        if include_shares:
            for share in source_doc.shares.all():
                Share.objects.create(
                    document=target_doc,
                    shared_with=share.shared_with,
                    permission_level=share.permission_level,
                    shared_by=share.shared_by,
                    expires_at=share.expires_at,
                )
                result["shares"] += 1

        return result


class PermissionTemplates:
    OWNER_PERMISSIONS = [
        "view_doc",
        "edit_doc",
        "delete_doc",
        "download_doc",
        "share_doc",
    ]

    EDITOR_PERMISSIONS = [
        "view_doc",
        "edit_doc",
        "download_doc",
    ]

    VIEWER_PERMISSIONS = [
        "view_doc",
    ]

    REVIEWER_PERMISSIONS = [
        "view_doc",
        "download_doc",
    ]

    @classmethod
    def apply_template(
        cls,
        template_name: str,
        user: User,
        document: Document,
    ) -> List[str]:
        templates = {
            "owner": cls.OWNER_PERMISSIONS,
            "editor": cls.EDITOR_PERMISSIONS,
            "viewer": cls.VIEWER_PERMISSIONS,
            "reviewer": cls.REVIEWER_PERMISSIONS,
        }

        permissions = templates.get(template_name, [])
        for perm in permissions:
            assign_perm(f"documents.{perm}", user, document)

        # Invalidate cache
        checker = CachedPermissionChecker(user)
        checker.invalidate_cache(document)

        return permissions


class PermissionQueryOptimizer:
    @staticmethod
    def get_documents_for_user(
        user: User,
        permissions: Union[str, List[str]],
        queryset: Optional[QuerySet] = None,
    ) -> QuerySet:
        if queryset is None:
            queryset = Document.objects.all()

        # Optimize with select_related and prefetch_related
        queryset = queryset.select_related(
            "owner",
            "created_by",
            "updated_by",
        ).prefetch_related(
            "shares",
            "shares__shared_with",
            "user_permissions",
            "group_permissions",
        )

        # Get documents user has permissions for
        docs_with_perms = get_objects_for_user(
            user,
            permissions,
            klass=queryset,
            use_groups=True,
            any_perm=isinstance(permissions, list),
        )

        # Also include documents shared with user
        shared_docs = queryset.filter(
            Q(shares__shared_with=user) | Q(owner=user) | Q(is_public=True)
        ).distinct()

        return docs_with_perms.union(shared_docs)

    @staticmethod
    def prefetch_permissions_for_queryset(
        queryset: QuerySet,
        user: User,
    ) -> Dict[int, Set[str]]:
        checker = ObjectPermissionChecker(user)
        checker.prefetch_perms(queryset)

        permissions_map = {}
        for doc in queryset:
            permissions_map[doc.id] = set(checker.get_perms(doc))

        return permissions_map


def check_document_access(
    user: User,
    document: Document,
    required_permission: str,
    use_cache: bool = True,
) -> bool:
    if document.owner == user:
        return True

    if document.is_public and required_permission in ["view_doc", "documents.view_doc"]:
        return True

    if required_permission in ["view_doc", "documents.view_doc"]:
        if document.shares.filter(
            shared_with=user,
            expires_at__isnull=True,
        ).exists():
            return True

    if use_cache:
        checker = CachedPermissionChecker(user)
        return checker.has_perm(required_permission, document)
    else:
        return user.has_perm(required_permission, document)


def get_user_document_permissions(user: User, document: Document) -> Dict[str, bool]:
    checker = CachedPermissionChecker(user)
    checker.prefetch_perms([document])

    permission_map = {
        "can_view": checker.has_perm("documents.view_doc", document),
        "can_edit": checker.has_perm("documents.edit_doc", document),
        "can_delete": checker.has_perm("documents.delete_doc", document),
        "can_download": checker.has_perm("documents.download_doc", document),
        "can_share": checker.has_perm("documents.share_doc", document),
        "is_owner": document.owner == user,
    }

    share = document.shares.filter(shared_with=user).first()
    if share:
        permission_map["shared_permission"] = share.permission_level
        permission_map["share_expires_at"] = share.expires_at

    return permission_map
