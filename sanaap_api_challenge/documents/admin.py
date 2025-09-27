from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from guardian.admin import GuardedModelAdmin

from .models import Access, Document, Share


class ShareInline(admin.TabularInline):
    model = Share
    extra = 0
    readonly_fields = ["shared_by", "created", "access_count", "last_accessed"]
    fields = [
        "shared_with",
        "permission_level",
        "shared_by",
        "expires_at",
        "access_count",
        "last_accessed",
    ]


@admin.register(Document)
class DocumentAdmin(GuardedModelAdmin):
    list_display = [
        "title",
        "owner",
        "file_name",
        "file_size_display",
        "content_type",
        "status",
        "download_count",
        "is_public",
        "modified",
    ]
    list_filter = [
        "status",
        "content_type",
        "is_public",
        "created",
        "modified",
    ]
    search_fields = ["title", "description", "file_name", "owner__username"]
    readonly_fields = [
        "file_path",
        "file_hash",
        "file_size",
        "download_count",
        "last_accessed",
        "created",
        "modified",
        "status_changed",
    ]
    inlines = [ShareInline]

    fieldsets = (
        (
            _("Basic Information"),
            {"fields": ("title", "description", "status")},
        ),
        (
            _("File Details"),
            {
                "fields": (
                    "file_name",
                    "file_path",
                    "file_size",
                    "content_type",
                    "file_hash",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            _("Ownership & Access"),
            {
                "fields": (
                    "owner",
                    "created_by",
                    "updated_by",
                    "is_public",
                )
            },
        ),
        (
            _("Statistics"),
            {
                "fields": ("download_count", "last_accessed"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": ("created", "modified", "status_changed"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("owner", "created_by", "updated_by")
        )

    def file_size_display(self, obj):
        return obj.get_human_readable_size()

    file_size_display.short_description = _("Size")
    file_size_display.admin_order_field = "file_size"

    def save_model(self, request, obj, form, change):
        if not change:  # Creating new object
            obj.created_by = request.user
            if not obj.owner:
                obj.owner = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = [
        "document",
        "shared_with",
        "permission_level",
        "shared_by",
        "is_active_display",
        "access_count",
        "created",
    ]
    list_filter = ["permission_level", "created", "expires_at"]
    search_fields = [
        "document__title",
        "shared_with__username",
        "shared_by__username",
    ]
    readonly_fields = [
        "shared_by",
        "created",
        "modified",
        "access_count",
        "last_accessed",
        "permission_changed",
    ]
    date_hierarchy = "created"

    fieldsets = (
        (
            _("Share Details"),
            {
                "fields": (
                    "document",
                    "shared_with",
                    "permission_level",
                    "shared_by",
                ),
            },
        ),
        (
            _("Expiration"),
            {"fields": ("expires_at",)},
        ),
        (
            _("Usage Statistics"),
            {
                "fields": ("access_count", "last_accessed"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": ("created", "modified", "permission_changed"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("document", "shared_with", "shared_by")
        )

    def is_active_display(self, obj):
        """Display if the share is active or expired."""
        if obj.expires_at is None:
            return format_html('<span style="color: blue;">Never Expires</span>')
        if obj.is_expired():
            return format_html('<span style="color: red;">Expired</span>')
        return format_html('<span style="color: green;">Active</span>')

    is_active_display.short_description = _("Status")

    def save_model(self, request, obj, form, change):
        """Set shared_by field automatically."""
        if not change:  # Creating new object
            obj.shared_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Access)
class AccessAdmin(admin.ModelAdmin):
    list_display = [
        "document_link",
        "user_link",
        "action",
        "success_display",
        "created",
        "ip_address",
    ]
    list_filter = ["action", "success", "created"]
    search_fields = ["document__title", "user__username", "ip_address"]
    readonly_fields = [
        "document",
        "user",
        "action",
        "created",
        "modified",
        "ip_address",
        "user_agent",
        "additional_info",
        "success",
        "error_message",
    ]
    date_hierarchy = "created"

    fieldsets = (
        (
            _("Access Details"),
            {
                "fields": (
                    "document",
                    "user",
                    "action",
                    "success",
                    "error_message",
                ),
            },
        ),
        (
            _("Request Information"),
            {
                "fields": ("ip_address", "user_agent"),
                "classes": ("collapse",),
            },
        ),
        (
            _("Additional Data"),
            {
                "fields": ("additional_info",),
                "classes": ("collapse",),
            },
        ),
        (
            _("Timestamps"),
            {
                "fields": ("created", "modified"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("document", "user")

    def document_link(self, obj):
        if obj.document:
            url = reverse("admin:documents_document_change", args=[obj.document.pk])
            return format_html('<a href="{}">{}</a>', url, obj.document.title)
        return "-"

    document_link.short_description = _("Document")
    document_link.admin_order_field = "document__title"

    def user_link(self, obj):
        """Display link to user admin page."""
        if obj.user:
            url = reverse("admin:auth_user_change", args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return _("Anonymous")

    user_link.short_description = _("User")
    user_link.admin_order_field = "user__username"

    def success_display(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">✓ Success</span>')
        return format_html('<span style="color: red;">✗ Failed</span>')

    success_display.short_description = _("Result")
    success_display.admin_order_field = "success"

    def has_add_permission(self, request):
        """Prevent manual creation of access logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent modification of access logs."""
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
