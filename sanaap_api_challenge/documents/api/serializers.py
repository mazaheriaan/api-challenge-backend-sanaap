from io import BytesIO

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from sanaap_api_challenge.documents.models import Access
from sanaap_api_challenge.documents.models import Document
from sanaap_api_challenge.documents.models import Share
from sanaap_api_challenge.documents.utils.validators import validate_uploaded_file
from sanaap_api_challenge.utils.minio_client import minio_client

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email"]
        read_only_fields = ["id", "username", "first_name", "last_name", "email"]


class ShareSerializer(serializers.ModelSerializer):
    shared_with = UserSerializer(read_only=True)
    shared_by = UserSerializer(read_only=True)
    shared_with_id = serializers.IntegerField(write_only=True)
    is_expired = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Share
        fields = [
            "id",
            "document",
            "shared_with",
            "shared_with_id",
            "shared_by",
            "permission_level",
            "created",
            "modified",
            "expires_at",
            "access_count",
            "last_accessed",
            "is_expired",
            "is_active",
            "permission_changed",
        ]
        read_only_fields = [
            "id",
            "document",
            "shared_by",
            "created",
            "modified",
            "access_count",
            "last_accessed",
            "permission_changed",
        ]

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_expired(self, obj):
        return obj.is_expired()

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_is_active(self, obj):
        return obj.is_active()

    def validate_shared_with_id(self, value):
        try:
            User.objects.get(id=value)
            return value
        except User.DoesNotExist:
            raise ValidationError(_("User not found."))

    def validate(self, attrs):
        if not self.instance and "document" not in self.context:
            raise ValidationError(
                _("Document context is required for creating shares."),
            )

        # Check if trying to share with owner
        document = (
            self.instance.document if self.instance else self.context.get("document")
        )
        shared_with_id = attrs.get("shared_with_id")
        if shared_with_id and document and shared_with_id == document.owner.id:
            raise ValidationError(_("Cannot share document with its owner."))

        # Check if trying to share with self
        request = self.context.get("request")
        if request and shared_with_id == request.user.id:
            raise ValidationError(_("Cannot share document with yourself."))

        return attrs

    def create(self, validated_data):
        shared_with_id = validated_data.pop("shared_with_id")
        shared_with = User.objects.get(id=shared_with_id)

        validated_data["shared_with"] = shared_with
        validated_data["shared_by"] = self.context["request"].user
        validated_data["document"] = self.context["document"]

        return super().create(validated_data)


class AccessLogSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    action_display = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = Access
        fields = [
            "id",
            "document",
            "user",
            "action",
            "action_display",
            "created",
            "modified",
            "ip_address",
            "user_agent",
            "additional_info",
            "success",
            "error_message",
        ]
        read_only_fields = [
            "id",
            "document",
            "user",
            "action",
            "action_display",
            "created",
            "modified",
            "ip_address",
            "user_agent",
            "additional_info",
            "success",
            "error_message",
        ]


class DocumentListSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    file_size_display = serializers.SerializerMethodField()
    file_extension = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    share_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "file_name",
            "file_size",
            "file_size_display",
            "file_extension",
            "content_type",
            "owner",
            "status",
            "status_display",
            "is_public",
            "download_count",
            "share_count",
            "created",
            "modified",
        ]
        read_only_fields = [
            "id",
            "file_size",
            "content_type",
            "owner",
            "download_count",
            "created",
            "modified",
            "share_count",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_file_size_display(self, obj):
        return obj.get_human_readable_size()

    @extend_schema_field(OpenApiTypes.STR)
    def get_file_extension(self, obj):
        return obj.get_file_extension()

    @extend_schema_field(OpenApiTypes.INT)
    def get_share_count(self, obj):
        return (
            obj.shares.filter(expires_at__isnull=True).count()
            + obj.shares.filter(expires_at__gt=timezone.now()).count()
        )


class DocumentDetailSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    updated_by = UserSerializer(read_only=True)
    shares = ShareSerializer(many=True, read_only=True)
    recent_access = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    file_extension = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_share = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "file_name",
            "file_path",
            "file_size",
            "file_size_display",
            "file_extension",
            "content_type",
            "file_hash",
            "owner",
            "created_by",
            "updated_by",
            "created",
            "modified",
            "status",
            "status_display",
            "status_changed",
            "is_public",
            "download_count",
            "last_accessed",
            "shares",
            "recent_access",
            "download_url",
            "can_edit",
            "can_share",
            "can_delete",
        ]
        read_only_fields = [
            "id",
            "file_path",
            "file_size",
            "content_type",
            "file_hash",
            "owner",
            "created_by",
            "updated_by",
            "created",
            "modified",
            "status_changed",
            "download_count",
            "last_accessed",
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_file_size_display(self, obj):
        return obj.get_human_readable_size()

    @extend_schema_field(OpenApiTypes.STR)
    def get_file_extension(self, obj):
        return obj.get_file_extension()

    @extend_schema_field(OpenApiTypes.STR)
    def get_download_url(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(f"/api/documents/{obj.id}/download/")
        return None

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_recent_access(self, obj):
        recent_logs = obj.access_logs.select_related("user")[:10]
        return AccessLogSerializer(recent_logs, many=True).data

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_edit(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user == obj.owner or request.user.has_perm("edit_doc", obj)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_share(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user == obj.owner or request.user.has_perm("share_doc", obj)

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_delete(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user == obj.owner or request.user.has_perm("delete_doc", obj)

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)

        if "request" in self.context:
            instance.updated_by = self.context["request"].user
            instance.save(update_fields=["updated_by", "modified"])

        return instance


class DocumentCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "file",
            "status",
            "is_public",
        ]
        read_only_fields = ["id"]

    def validate_file(self, file):
        is_valid, errors = validate_uploaded_file(file)

        if not is_valid:
            error_message = "; ".join(errors)
            raise ValidationError(error_message)

        return file

    def create(self, validated_data):
        """Create document with file upload to MinIO."""
        file = validated_data.pop("file")
        request = self.context.get("request")

        try:
            file_content = file.read()
            file.seek(0)

            file_hash = Document.calculate_file_hash(file_content)

            existing = Document.objects.filter(file_hash=file_hash).first()
            if existing:
                raise ValidationError(
                    _("A document with identical content already exists: %(title)s")
                    % {"title": existing.title},
                )

            file_path = Document.generate_file_path(file.name, request.user.id)

            file_obj = BytesIO(file_content)
            success = minio_client.upload_file(
                object_name=file_path,
                file_data=file_obj,
                file_size=len(file_content),
                content_type=file.content_type or "application/octet-stream",
            )

            if not success:
                raise ValidationError(_("Failed to upload file to storage"))

            validated_data.update(
                {
                    "file_name": file.name,
                    "file_path": file_path,
                    "file_size": len(file_content),
                    "content_type": file.content_type or "application/octet-stream",
                    "file_hash": file_hash,
                    "owner": request.user,
                    "created_by": request.user,
                },
            )

            document = super().create(validated_data)

            Access.objects.create(
                document=document,
                user=request.user,
                action="upload",
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                success=True,
            )

            return document

        except Exception as e:
            # Clean up uploaded file if document creation fails
            if "file_path" in locals():
                minio_client.delete_file(file_path)

            if request:
                Access.objects.create(
                    document=None,
                    user=request.user,
                    action="upload",
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    success=False,
                    error_message=str(e),
                    additional_info={"filename": file.name},
                )

            if isinstance(e, ValidationError):
                raise e
            raise ValidationError(
                _("Failed to create document: %(error)s") % {"error": str(e)},
            )

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


class BulkShareSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=50,
        help_text=_("List of user IDs to share with"),
    )
    permission_level = serializers.ChoiceField(
        choices=Share.PERMISSION_LEVEL,
        default="view",
        help_text=_("Permission level for all shares"),
    )
    expires_at = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text=_("Optional expiration date for all shares"),
    )

    def validate_user_ids(self, value):
        existing_ids = set(
            User.objects.filter(id__in=value).values_list("id", flat=True),
        )
        invalid_ids = set(value) - existing_ids

        if invalid_ids:
            raise ValidationError(
                _("The following user IDs do not exist: %(ids)s")
                % {"ids": ", ".join(map(str, invalid_ids))},
            )

        return value
