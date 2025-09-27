import hashlib
import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from guardian.models import GroupObjectPermissionBase
from guardian.models import UserObjectPermissionBase
from model_utils import Choices
from model_utils.fields import MonitorField
from model_utils.fields import StatusField
from model_utils.models import StatusModel
from model_utils.models import TimeStampedModel

User = get_user_model()


class Document(TimeStampedModel, StatusModel):
    STATUS = Choices(
        ("draft", "Draft"),
        ("active", "Active"),
        ("archived", "Archived"),
        ("deleted", "Deleted"),
    )

    # File information
    title = models.CharField(max_length=255, help_text=_("Document title"))
    description = models.TextField(blank=True, help_text=_("Document description"))
    file_name = models.CharField(max_length=255, help_text=_("Original filename"))
    file_path = models.CharField(
        max_length=500,
        unique=True,
        help_text=_("MinIO object path"),
    )
    file_size = models.PositiveBigIntegerField(help_text=_("File size in bytes"))
    content_type = models.CharField(max_length=100, help_text=_("MIME type"))
    file_hash = models.CharField(
        max_length=64,
        unique=True,
        help_text=_("SHA-256 hash for deduplication and integrity"),
    )

    # Ownership and access
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_documents",
        help_text=_("Document owner"),
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_documents",
        help_text=_("User who created this document"),
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_documents",
        help_text=_("User who last updated this document"),
    )

    # Access control
    is_public = models.BooleanField(
        default=False,
        help_text=_("Whether the document is publicly accessible"),
    )

    # Usage tracking
    download_count = models.PositiveIntegerField(
        default=0,
        help_text=_("Number of times this document has been downloaded"),
    )
    last_accessed = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the document was last accessed"),
    )

    class Meta:
        ordering = ["-modified"]
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")
        permissions = [
            ("view_doc", _("Can view document")),
            ("edit_doc", _("Can edit document")),
            ("delete_doc", _("Can delete document")),
            ("download_doc", _("Can download document")),
            ("share_doc", _("Can share document")),
        ]
        indexes = [
            models.Index(fields=["owner", "-created"]),
            models.Index(fields=["file_hash"]),
            models.Index(fields=["content_type"]),
            models.Index(fields=["-modified"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("api:document-detail", kwargs={"pk": self.pk})

    def get_file_extension(self):
        return self.file_name.split(".")[-1].lower() if "." in self.file_name else ""

    def get_human_readable_size(self):
        size = self.file_size
        size_limit = 1024.0
        for unit in ["B", "KB", "MB", "GB"]:
            if size < size_limit:
                return f"{size:.1f} {unit}"
            size /= size_limit
        return f"{size:.1f} TB"

    def increment_download_count(self):
        self.download_count = models.F("download_count") + 1
        self.last_accessed = timezone.now()
        self.save(update_fields=["download_count", "last_accessed"])

    @staticmethod
    def calculate_file_hash(file_content):
        return hashlib.sha256(file_content).hexdigest()

    @staticmethod
    def generate_file_path(original_filename, owner_id):
        """Generate a unique file path for MinIO storage."""
        now = timezone.now()
        unique_id = uuid.uuid4().hex
        filename = f"{unique_id}_{original_filename}"

        return (
            f"documents/{now.year}/{now.month:02d}/{now.day:02d}/{owner_id}/{filename}"
        )


class Share(TimeStampedModel):
    PERMISSION_LEVEL = Choices(
        ("view", _("View Only")),
        ("edit", _("Can Edit")),
        ("download", _("Can Download")),
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    shared_with = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shared_documents",
        help_text=_("User the document is shared with"),
    )
    permission_level = StatusField(
        choices_name="PERMISSION_LEVEL",
        default="view",
        help_text=_("Permission level for the shared user"),
    )
    shared_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="documents_shared_by_me",
        help_text=_("User who shared the document"),
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the share expires (optional)"),
    )

    # Usage tracking
    access_count = models.PositiveIntegerField(
        default=0,
        help_text=_("Number of times the shared user accessed the document"),
    )
    last_accessed = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the shared user last accessed the document"),
    )

    # Monitor when permission level changes
    permission_changed = MonitorField(monitor="permission_level")

    class Meta:
        verbose_name = _("Share")
        verbose_name_plural = _("Shares")
        unique_together = ["document", "shared_with"]
        indexes = [
            models.Index(fields=["shared_with", "-created"]),
            models.Index(fields=["document", "permission_level"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        share_str = f"{self.document.title} shared with {self.shared_with.username}"
        return f"{share_str} ({self.permission_level})"

    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at

    def is_active(self):
        return not self.is_expired()

    def increment_access_count(self):
        self.access_count = models.F("access_count") + 1
        self.last_accessed = timezone.now()
        self.save(update_fields=["access_count", "last_accessed"])


class Access(TimeStampedModel):
    """Audit log for document access"""

    ACTION = Choices(
        ("view", "Viewed"),
        ("download", "Downloaded"),
        ("upload", "Uploaded"),
        ("edit", "Edited"),
        ("delete", "Deleted"),
        ("share", "Shared"),
        ("unshare", "Unshared"),
        ("restore", "Restored"),
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="access_logs",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="document_accesses",
    )
    action = StatusField(
        choices_name="ACTION",
        help_text=_("Action performed on the document"),
    )

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    additional_info = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Additional information about the access"),
    )

    # Track result of action
    success = models.BooleanField(
        default=True,
        help_text=_("Whether the action was successful"),
    )
    error_message = models.TextField(
        blank=True,
        help_text=_("Error message if action failed"),
    )

    class Meta:
        verbose_name = _("Access Log")
        verbose_name_plural = _("Access Logs")
        ordering = ["-created"]
        indexes = [
            models.Index(fields=["document", "-created"]),
            models.Index(fields=["user", "-created"]),
            models.Index(fields=["action", "-created"]),
            models.Index(fields=["success", "-created"]),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else _("Anonymous")
        status = _("✓") if self.success else _("✗")
        return f"{status} {user_str} {self.action} {self.document.title}"


# Performance-optimized Guardian permission models with direct foreign keys
class DocumentUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="user_permissions"
    )

    class Meta:
        indexes = [
            models.Index(fields=["user", "permission"]),
            models.Index(fields=["content_object", "permission"]),
            models.Index(fields=["user", "content_object", "permission"]),
        ]
        verbose_name = _("Document User Permission")
        verbose_name_plural = _("Document User Permissions")


class DocumentGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="group_permissions"
    )

    class Meta:
        indexes = [
            models.Index(fields=["group", "permission"]),
            models.Index(fields=["content_object", "permission"]),
            models.Index(fields=["group", "content_object", "permission"]),
        ]
        verbose_name = _("Document Group Permission")
        verbose_name_plural = _("Document Group Permissions")
