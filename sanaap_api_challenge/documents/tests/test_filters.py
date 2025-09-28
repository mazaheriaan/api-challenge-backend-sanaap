from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from sanaap_api_challenge.documents.api.filters import AccessFilter
from sanaap_api_challenge.documents.api.filters import DocumentFilter
from sanaap_api_challenge.documents.api.filters import ShareFilter

from .factories import AccessFactory
from .factories import DocumentFactory
from .factories import ShareFactory
from .factories import UserFactory

User = get_user_model()


class TestDocumentFilter(TestCase):
    def test_title_filter(self):
        doc1 = DocumentFactory(title="Python Programming Guide")
        doc2 = DocumentFactory(title="JavaScript Handbook")
        doc3 = DocumentFactory(title="React Tutorial")

        filter_set = DocumentFilter(data={"title": "Python"})
        queryset = filter_set.qs

        assert doc1 in queryset
        assert doc2 not in queryset
        assert doc3 not in queryset

    def test_owner_filter(self):
        user1 = UserFactory()
        user2 = UserFactory()
        doc1 = DocumentFactory(owner=user1)
        doc2 = DocumentFactory(owner=user2)

        filter_set = DocumentFilter(data={"owner": user1.id})
        queryset = filter_set.qs

        assert doc1 in queryset
        assert doc2 not in queryset

    def test_invalid_filter_values(self):
        DocumentFactory()

        filter_set = DocumentFilter(data={"owner": "invalid"})
        queryset = filter_set.qs
        # Should handle gracefully and return integer count
        assert isinstance(queryset.count(), int)

    def test_search_filter(self):
        doc1 = DocumentFactory(title="Advanced Python")
        doc2 = DocumentFactory(title="Basic Java")
        doc3 = DocumentFactory(description="Python programming language")

        filter_set = DocumentFilter(data={"search": "Python"})
        queryset = filter_set.qs

        assert doc1 in queryset
        assert doc2 not in queryset
        # Search should work on description too
        assert doc3 in queryset

    def test_is_public_filter(self):
        public_doc = DocumentFactory(is_public=True)
        private_doc = DocumentFactory(is_public=False)

        filter_set = DocumentFilter(data={"is_public": True})
        queryset = filter_set.qs

        assert public_doc in queryset
        assert private_doc not in queryset

    def test_multiple_filters(self):
        user = UserFactory()
        doc1 = DocumentFactory(title="Python Guide", owner=user, is_public=True)
        doc2 = DocumentFactory(title="Python Guide", owner=user, is_public=False)
        doc3 = DocumentFactory(title="Java Guide", owner=user, is_public=True)

        filter_set = DocumentFilter(
            data={
                "title": "Python",
                "owner": user.id,
                "is_public": True,
            },
        )
        queryset = filter_set.qs

        assert doc1 in queryset
        assert doc2 not in queryset
        assert doc3 not in queryset


class TestShareFilter(TestCase):
    def test_document_filter(self):
        doc1 = DocumentFactory()
        doc2 = DocumentFactory()
        share1 = ShareFactory(document=doc1)
        share2 = ShareFactory(document=doc2)

        filter_set = ShareFilter(data={"document": doc1.id})
        queryset = filter_set.qs

        assert share1 in queryset
        assert share2 not in queryset

    def test_shared_with_filter(self):
        user1 = UserFactory()
        user2 = UserFactory()
        share1 = ShareFactory(shared_with=user1)
        share2 = ShareFactory(shared_with=user2)

        filter_set = ShareFilter(data={"shared_with": user1.id})
        queryset = filter_set.qs

        assert share1 in queryset
        assert share2 not in queryset

    def test_permission_level_filter(self):
        share1 = ShareFactory(permission_level="view")
        share2 = ShareFactory(permission_level="edit")

        filter_set = ShareFilter(data={"permission_level": "view"})
        queryset = filter_set.qs

        assert share1 in queryset
        assert share2 not in queryset

    def test_expires_after_filter(self):
        future_time = timezone.now() + timedelta(days=1)
        share1 = ShareFactory(expires_at=future_time)
        share2 = ShareFactory(expires_at=None)

        # Use expires_after filter which exists in the actual ShareFilter
        filter_set = ShareFilter(data={"expires_after": future_time})
        queryset = filter_set.qs

        assert share1 in queryset
        assert share2 not in queryset

    def test_is_active_filter(self):
        # Active share (not expired)
        future_time = timezone.now() + timedelta(days=1)
        active_share = ShareFactory(expires_at=future_time)

        # Expired share
        past_time = timezone.now() - timedelta(days=1)
        expired_share = ShareFactory(expires_at=past_time)

        filter_set = ShareFilter(data={"is_active": True})
        queryset = filter_set.qs

        assert active_share in queryset
        assert expired_share not in queryset


class TestAccessFilter(TestCase):
    def test_document_filter(self):
        doc1 = DocumentFactory()
        doc2 = DocumentFactory()
        access1 = AccessFactory(document=doc1)
        access2 = AccessFactory(document=doc2)

        filter_set = AccessFilter(data={"document": doc1.id})
        queryset = filter_set.qs

        assert access1 in queryset
        assert access2 not in queryset

    def test_user_filter(self):
        user1 = UserFactory()
        user2 = UserFactory()
        access1 = AccessFactory(user=user1)
        access2 = AccessFactory(user=user2)

        filter_set = AccessFilter(data={"user": user1.id})
        queryset = filter_set.qs

        assert access1 in queryset
        assert access2 not in queryset

    def test_action_filter(self):
        access1 = AccessFactory(action="view")
        access2 = AccessFactory(action="download")

        filter_set = AccessFilter(data={"action": "view"})
        queryset = filter_set.qs

        assert access1 in queryset
        assert access2 not in queryset

    def test_success_filter(self):
        successful_access = AccessFactory(success=True)
        failed_access = AccessFactory(success=False)

        filter_set = AccessFilter(data={"success": True})
        queryset = filter_set.qs

        assert successful_access in queryset
        assert failed_access not in queryset

    def test_created_after_filter(self):
        today = timezone.now()
        yesterday = today - timedelta(days=1)

        today_access = AccessFactory()
        yesterday_access = AccessFactory()
        yesterday_access.created = yesterday
        yesterday_access.save()

        # Use created_after filter which exists in the AccessFilter
        filter_set = AccessFilter(data={"created_after": today})
        queryset = filter_set.qs

        assert today_access in queryset
        assert yesterday_access not in queryset

    def test_ip_address_filter(self):
        access1 = AccessFactory(ip_address="192.168.1.1")
        access2 = AccessFactory(ip_address="10.0.0.1")

        filter_set = AccessFilter(data={"ip_address": "192.168.1.1"})
        queryset = filter_set.qs

        assert access1 in queryset
        assert access2 not in queryset
