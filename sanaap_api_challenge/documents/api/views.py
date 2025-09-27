from django.db.models import Count
from django.db.models import Q
from django.http import Http404
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from sanaap_api_challenge.documents.models import Access
from sanaap_api_challenge.documents.models import Document
from sanaap_api_challenge.documents.models import Share
from sanaap_api_challenge.utils.minio_client import minio_client

from .filters import DocumentFilter
from .filters import ShareFilter
from .pagination import DocumentPagination
from .permissions import CanShareDocument
from .permissions import DocumentPermission
from .permissions import SharePermission
from .serializers import AccessLogSerializer
from .serializers import BulkShareSerializer
from .serializers import DocumentCreateSerializer
from .serializers import DocumentDetailSerializer
from .serializers import DocumentListSerializer
from .serializers import ShareSerializer
from .utils import get_client_ip


def log_document_access(  # noqa: PLR0913
    document,
    user,
    action,
    request,
    additional_info=None,
    success=True,  # noqa: FBT002
    error_message="",
):
    Access.objects.create(
        document=document,
        user=user,
        action=action,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        additional_info=additional_info or {},
        success=success,
        error_message=error_message,
    )


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related(
        "owner",
        "created_by",
        "updated_by",
    ).prefetch_related("shares")

    permission_classes = [IsAuthenticated, DocumentPermission]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = DocumentFilter
    search_fields = ["title", "description", "file_name"]
    ordering_fields = [
        "created",
        "modified",
        "title",
        "file_size",
        "download_count",
        "status",
    ]
    ordering = ["-modified"]
    pagination_class = DocumentPagination

    http_method_names = ["get", "post", "delete", "head", "options"]

    @extend_schema(
        operation_id="documents_create",
        summary="Upload a new document",
        description=(
            "Create a new document by uploading a file. "
            "The file will be stored in MinIO object storage."
        ),
        request=DocumentCreateSerializer,
        responses={201: DocumentDetailSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == "list":
            return DocumentListSerializer
        if self.action == "create":
            return DocumentCreateSerializer
        return DocumentDetailSerializer

    def get_queryset(self):
        """Filter documents based on user access."""
        user = self.request.user

        if user.is_superuser:
            return self.queryset

        # Return documents that user can access:
        # 1. Documents owned by user
        # 2. Documents shared with user (not expired)
        # 3. Public documents
        return self.queryset.filter(
            Q(owner=user)
            | Q(shares__shared_with=user, shares__expires_at__isnull=True)
            | Q(shares__shared_with=user, shares__expires_at__gt=timezone.now())
            | Q(is_public=True),
        ).distinct()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        # Save document with current user as owner
        serializer.save(owner=self.request.user, created_by=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()

        log_document_access(instance, request.user, "view", request)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        instance.status = "deleted"
        instance.save()

        log_document_access(instance, request.user, "delete", request)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()

        # Check download permission
        if not (
            request.user == document.owner
            or request.user.has_perm("download_doc", document)
            or document.is_public
            or document.shares.filter(
                shared_with=request.user,
                permission_level__in=["download", "edit"],
            )
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .exists()
        ):
            return Response(
                {"detail": _("You don't have permission to download this document.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            file_data = minio_client.get_file_data(document.file_path)

            if not file_data:
                raise Http404(_("File not found in storage"))

            document.increment_download_count()

            log_document_access(document, request.user, "download", request)

            response = HttpResponse(file_data, content_type=document.content_type)
            response["Content-Disposition"] = (
                f'attachment; filename="{document.file_name}"'
            )
            response["Content-Length"] = len(file_data)

            return response

        except Exception as e:
            log_document_access(
                document,
                request.user,
                "download",
                request,
                success=False,
                error_message=str(e),
            )
            return Response(
                {"detail": _("Failed to download file: %(error)s") % {"error": str(e)}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["get"])
    def shares(self, request, pk=None):
        document = self.get_object()

        if not (
            request.user == document.owner
            or request.user.has_perm("share_doc", document)
        ):
            return Response(
                {
                    "detail": _(
                        "You don't have permission to view shares for this document.",
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        shares = document.shares.select_related("shared_with", "shared_by")
        serializer = ShareSerializer(shares, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, CanShareDocument],
    )
    def share(self, request, pk=None):
        """Share document with another user."""
        document = self.get_object()

        # Check if already shared with this user
        shared_with_id = request.data.get("shared_with_id")
        if document.shares.filter(shared_with_id=shared_with_id).exists():
            return Response(
                {"detail": _("Document is already shared with this user.")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create share
        serializer = ShareSerializer(
            data=request.data,
            context={"request": request, "document": document},
        )
        serializer.is_valid(raise_exception=True)
        share = serializer.save()

        # Log the action
        log_document_access(
            document,
            request.user,
            "share",
            request,
            {
                "shared_with": share.shared_with.username,
                "permission_level": share.permission_level,
            },
        )

        return Response(ShareSerializer(share).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, CanShareDocument],
    )
    def bulk_share(self, request, pk=None):
        """Share document with multiple users."""
        document = self.get_object()

        serializer = BulkShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_ids = serializer.validated_data["user_ids"]
        permission_level = serializer.validated_data["permission_level"]
        expires_at = serializer.validated_data.get("expires_at")

        created_shares = []
        for user_id in user_ids:
            # Skip if already shared or if user is owner
            if (
                document.shares.filter(shared_with_id=user_id).exists()
                or user_id == document.owner.id
            ):
                continue

            share = Share.objects.create(
                document=document,
                shared_with_id=user_id,
                shared_by=request.user,
                permission_level=permission_level,
                expires_at=expires_at,
            )
            created_shares.append(share)

        # Log the action
        if created_shares:
            log_document_access(
                document,
                request.user,
                "share",
                request,
                {
                    "shared_count": len(created_shares),
                    "permission_level": permission_level,
                },
            )

        return Response(
            {
                "created": len(created_shares),
                "shares": ShareSerializer(created_shares, many=True).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path="shares/(?P<share_id>[0-9]+)")
    def unshare(self, request, pk=None, share_id=None):
        """Remove a share from a document."""
        document = self.get_object()

        # Only owner can unshare
        if request.user != document.owner:
            return Response(
                {"detail": _("Only the document owner can remove shares.")},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            share = document.shares.get(id=share_id)
            username = share.shared_with.username

            # Log before deleting
            log_document_access(
                document,
                request.user,
                "unshare",
                request,
                {"unshared_from": username},
            )

            share.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        except Share.DoesNotExist:
            return Response(
                {"detail": _("Share not found.")},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get"])
    def access_logs(self, request, pk=None):
        document = self.get_object()

        if not (request.user == document.owner or request.user.is_superuser):
            return Response(
                {
                    "detail": _(
                        "You don't have permission to view access logs for this document.",
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        logs = document.access_logs.select_related("user").order_by("-created")
        page = self.paginate_queryset(logs)

        if page is not None:
            serializer = AccessLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = AccessLogSerializer(logs, many=True)
        return Response(serializer.data)


class ShareViewSet(viewsets.ModelViewSet):
    queryset = Share.objects.select_related("document", "shared_with", "shared_by")
    serializer_class = ShareSerializer
    permission_classes = [IsAuthenticated, SharePermission]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ShareFilter
    ordering = ["-created"]
    http_method_names = [
        "get",
        "patch",
        "delete",
        "head",
        "options",
    ]

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            return self.queryset

        # Users can see:
        # 1. Shares they created
        # 2. Shares where they are the recipient
        # 3. Shares for documents they own
        return self.queryset.filter(
            Q(shared_by=user) | Q(shared_with=user) | Q(document__owner=user),
        ).distinct()

    def perform_update(self, serializer):
        share = serializer.save()

        log_document_access(
            share.document,
            self.request.user,
            "edit",
            self.request,
            {
                "share_id": share.id,
                "permission_level": share.permission_level,
            },
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        log_document_access(
            instance.document,
            request.user,
            "unshare",
            request,
            {
                "unshared_from": instance.shared_with.username,
                "permission_level": instance.permission_level,
            },
        )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="documents_my_documents",
        summary="Get user's documents",
        description="Get documents owned by the user and documents shared with them",
        responses={200: DocumentListSerializer(many=True)},
        tags=["documents"],
    )
    def get(self, request):
        user = request.user

        owned = Document.objects.filter(owner=user, status="active").annotate(
            share_count=Count("shares"),
        )

        shared_ids = (
            Share.objects.filter(shared_with=user)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .values_list("document_id", flat=True)
        )
        shared = Document.objects.filter(id__in=shared_ids, status="active").annotate(
            share_count=Count("shares"),
        )

        owned_serializer = DocumentListSerializer(
            owned,
            many=True,
            context={"request": request},
        )
        shared_serializer = DocumentListSerializer(
            shared,
            many=True,
            context={"request": request},
        )

        return Response(
            {
                "owned": owned_serializer.data,
                "shared": shared_serializer.data,
                "stats": {
                    "total_owned": owned.count(),
                    "total_shared": shared.count(),
                    "total_size": sum(doc.file_size for doc in owned),
                },
            },
        )


class PublicDocumentsView(APIView):
    permission_classes = []

    @extend_schema(
        operation_id="documents_public",
        summary="Get public documents",
        description="Get all publicly available documents with pagination",
        responses={200: DocumentListSerializer(many=True)},
        tags=["documents"],
    )
    def get(self, request):
        documents = Document.objects.filter(
            is_public=True,
            status="active",
        ).select_related("owner")

        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(documents, request)

        serializer = DocumentListSerializer(
            page,
            many=True,
            context={"request": request},
        )

        return paginator.get_paginated_response(serializer.data)
