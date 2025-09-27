from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions
from rest_framework.request import Request
from rest_framework.views import APIView

from sanaap_api_challenge.documents.models import Document
from sanaap_api_challenge.documents.models import Share

User = get_user_model()


class DocumentPermission(permissions.BasePermission):
    """
    Permission class for Document operations.

    - Anyone authenticated can list documents (filtered by access)
    - Anyone authenticated can create documents
    - Only owners can delete documents
    - View access requires: owner, shared with user, or public document
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.user.is_authenticated

    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        obj: Document,
    ) -> bool:
        user = request.user

        if user.is_superuser:
            return True

        if obj.owner == user:
            return True

        if request.method in permissions.SAFE_METHODS:
            if obj.is_public:
                return True

            return (
                obj.shares.filter(
                    shared_with=user,
                )
                .filter(
                    Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()),
                )
                .exists()
            )

        if request.method == "DELETE":
            return False

        return False


class SharePermission(permissions.BasePermission):
    """
    Permission class for Share operations.

    Rules:
    - Only document owner or users with share permission can create/modify shares
    - Users can view shares they created or are part of
    - Only document owner or share creator can delete a share
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        return request.user.is_authenticated

    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        obj: Share,
    ) -> bool:
        user = request.user

        if user.is_superuser:
            return True

        document = obj.document

        if request.method in permissions.SAFE_METHODS:
            return user in (document.owner, obj.shared_with, obj.shared_by)

        return user in (document.owner, obj.shared_by)


class CanShareDocument(permissions.BasePermission):
    """
    Permission to check if user can share a document.

    Rules:
    - Document owner can always share
    - Users with explicit share permission can share
    """

    def has_object_permission(
        self,
        request: Request,
        view: APIView,
        obj: Document,
    ) -> bool:
        user = request.user

        if user.is_superuser:
            return True

        return obj.owner == user
