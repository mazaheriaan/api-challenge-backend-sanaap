from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters

from sanaap_api_challenge.documents.models import Access
from sanaap_api_challenge.documents.models import Document
from sanaap_api_challenge.documents.models import Share

User = get_user_model()


class DocumentFilter(filters.FilterSet):
    title = filters.CharFilter(lookup_expr="icontains")
    description = filters.CharFilter(lookup_expr="icontains")
    file_name = filters.CharFilter(lookup_expr="icontains")

    status = filters.ChoiceFilter(choices=Document.STATUS)
    is_public = filters.BooleanFilter()

    owner = filters.ModelChoiceFilter(queryset=User.objects.all())
    owner_username = filters.CharFilter(
        field_name="owner__username",
        lookup_expr="icontains",
    )

    created_after = filters.DateTimeFilter(field_name="created", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created", lookup_expr="lte")
    modified_after = filters.DateTimeFilter(field_name="modified", lookup_expr="gte")
    modified_before = filters.DateTimeFilter(field_name="modified", lookup_expr="lte")

    min_size = filters.NumberFilter(field_name="file_size", lookup_expr="gte")
    max_size = filters.NumberFilter(field_name="file_size", lookup_expr="lte")

    content_type = filters.CharFilter(lookup_expr="icontains")
    file_extension = filters.CharFilter(method="filter_by_extension")

    shared_with = filters.ModelChoiceFilter(
        field_name="shares__shared_with",
        queryset=User.objects.all(),
    )
    shared_with_me = filters.BooleanFilter(method="filter_shared_with_me")
    has_shares = filters.BooleanFilter(method="filter_has_shares")

    min_downloads = filters.NumberFilter(field_name="download_count", lookup_expr="gte")
    max_downloads = filters.NumberFilter(field_name="download_count", lookup_expr="lte")

    # Combined search across multiple fields
    search = filters.CharFilter(method="search_filter")

    class Meta:
        model = Document
        fields = [
            "title",
            "description",
            "file_name",
            "status",
            "is_public",
            "owner",
            "owner_username",
            "created_after",
            "created_before",
            "modified_after",
            "modified_before",
            "min_size",
            "max_size",
            "content_type",
            "file_extension",
            "shared_with",
            "shared_with_me",
            "has_shares",
            "min_downloads",
            "max_downloads",
            "search",
        ]

    def filter_by_extension(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(file_name__iendswith=f".{value}")

    def filter_shared_with_me(self, queryset, name, value):
        """Filter documents shared with the current user."""
        if not value:
            return queryset

        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()

        shared_ids = (
            Share.objects.filter(shared_with=user)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
            .values_list("document_id", flat=True)
        )

        return queryset.filter(id__in=shared_ids)

    def filter_has_shares(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(shares__expires_at__isnull=True)
                | Q(shares__expires_at__gt=timezone.now()),
            ).distinct()
        return queryset.exclude(
            Q(shares__expires_at__isnull=True)
            | Q(shares__expires_at__gt=timezone.now()),
        ).distinct()

    def search_filter(self, queryset, name, value):
        """Combined search across multiple fields."""
        if not value:
            return queryset

        return queryset.filter(
            Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(file_name__icontains=value)
            | Q(owner__username__icontains=value)
            | Q(owner__first_name__icontains=value)
            | Q(owner__last_name__icontains=value),
        ).distinct()


class ShareFilter(filters.FilterSet):
    document = filters.ModelChoiceFilter(queryset=Document.objects.all())
    document_title = filters.CharFilter(
        field_name="document__title",
        lookup_expr="icontains",
    )

    shared_with = filters.ModelChoiceFilter(queryset=User.objects.all())
    shared_by = filters.ModelChoiceFilter(queryset=User.objects.all())
    shared_with_username = filters.CharFilter(
        field_name="shared_with__username",
        lookup_expr="icontains",
    )

    permission_level = filters.ChoiceFilter(choices=Share.PERMISSION_LEVEL)

    created_after = filters.DateTimeFilter(field_name="created", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created", lookup_expr="lte")
    expires_after = filters.DateTimeFilter(field_name="expires_at", lookup_expr="gte")
    expires_before = filters.DateTimeFilter(field_name="expires_at", lookup_expr="lte")

    is_active = filters.BooleanFilter(method="filter_active")
    is_expired = filters.BooleanFilter(method="filter_expired")

    min_access = filters.NumberFilter(field_name="access_count", lookup_expr="gte")
    max_access = filters.NumberFilter(field_name="access_count", lookup_expr="lte")

    class Meta:
        model = Share
        fields = [
            "document",
            "document_title",
            "shared_with",
            "shared_by",
            "shared_with_username",
            "permission_level",
            "created_after",
            "created_before",
            "expires_after",
            "expires_before",
            "is_active",
            "is_expired",
            "min_access",
            "max_access",
        ]

    def filter_active(self, queryset, name, value):
        now = timezone.now()
        if value:
            return queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        return queryset.filter(expires_at__lte=now)

    def filter_expired(self, queryset, name, value):
        now = timezone.now()
        if value:
            return queryset.filter(expires_at__lte=now)
        return queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))


class AccessFilter(filters.FilterSet):
    document = filters.ModelChoiceFilter(queryset=Document.objects.all())
    document_title = filters.CharFilter(
        field_name="document__title",
        lookup_expr="icontains",
    )

    user = filters.ModelChoiceFilter(queryset=User.objects.all())
    username = filters.CharFilter(field_name="user__username", lookup_expr="icontains")

    action = filters.ChoiceFilter(choices=Access.ACTION)

    created_after = filters.DateTimeFilter(field_name="created", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created", lookup_expr="lte")

    success = filters.BooleanFilter()

    ip_address = filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Access
        fields = [
            "document",
            "document_title",
            "user",
            "username",
            "action",
            "created_after",
            "created_before",
            "success",
            "ip_address",
        ]
