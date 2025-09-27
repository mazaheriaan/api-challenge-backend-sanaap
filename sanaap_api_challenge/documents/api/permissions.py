from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from sanaap_api_challenge.documents.models import Document
from sanaap_api_challenge.documents.models import Share
from sanaap_api_challenge.documents.utils.permissions import CachedPermissionChecker
from sanaap_api_challenge.documents.utils.permissions import check_document_access

User = get_user_model()


class BaseDocumentPermission(permissions.BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user.is_authenticated:
            return False

        # Superusers have full access
        if request.user.is_superuser:
            return True

        if self._check_group_permission(request.user):
            return True

        return self._check_view_permission(request, view)

    def _check_group_permission(self, user: User) -> bool:
        cache_key = f"user_groups:{user.id}"
        cached_groups = cache.get(cache_key)

        if cached_groups is None:
            cached_groups = list(user.groups.values_list("name", flat=True))
            cache.set(cache_key, cached_groups, 300)  # 5 minutes

        return "document_admins" in cached_groups

    def _check_view_permission(self, request: Request, view: APIView) -> bool:
        return True


class DocumentPermission(BaseDocumentPermission):
    PERMISSION_MAPPING = {
        "GET": "view_doc",
        "POST": "add_document",
        "DELETE": "delete_doc",
    }

    def _check_view_permission(self, request: Request, view: APIView) -> bool:
        if view.action == "list":
            return True

        if view.action == "create":
            return self._can_create_document(request.user)

        return True

    def _can_create_document(self, user: User) -> bool:
        cache_key = f"can_create_doc:{user.id}"
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            return cached_result

        # Check if user is in editor/admin groups or has permission
        result = user.groups.filter(
            name__in=["document_admins", "document_editors"],
        ).exists() or user.has_perm("documents.add_document")

        cache.set(cache_key, result, 300)
        return result

    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        obj: Document,
    ) -> bool:
        user = request.user

        if user.is_superuser or self._check_group_permission(user):
            return True

        if obj.owner == user:
            return True

        checker = CachedPermissionChecker(user)

        # Map HTTP methods to required permissions
        if request.method in permissions.SAFE_METHODS:
            return self._check_read_permission(user, obj, checker)
        if request.method == "DELETE":
            return checker.has_perm("documents.delete_doc", obj)

        return False

    def _check_read_permission(
        self,
        user: User,
        obj: Document,
        checker: CachedPermissionChecker,
    ) -> bool:
        if checker.has_perm("documents.view_doc", obj):
            return True

        if obj.is_public:
            return True

        return Share.objects.filter(
            Q(document=obj, shared_with=user)
            & (Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())),
        ).exists()


class CanShareDocument(BaseDocumentPermission):
    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        obj: Document,
    ) -> bool:
        user = request.user

        if obj.owner == user:
            return True

        return check_document_access(user, obj, "documents.share_doc")
