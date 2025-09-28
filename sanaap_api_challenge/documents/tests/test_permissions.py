from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.request import Request

from sanaap_api_challenge.documents.api.permissions import CanShareDocument
from sanaap_api_challenge.documents.api.permissions import DocumentPermission
from sanaap_api_challenge.documents.api.permissions import SharePermission

from .factories import DocumentFactory
from .factories import ExpiredShareFactory
from .factories import ShareFactory
from .factories import SuperuserFactory
from .factories import UserFactory

User = get_user_model()


def create_mock_request(user, method="GET"):
    """Helper to create a mock request with a user and method."""
    request = Mock(spec=Request)
    request.user = user
    request.method = method
    return request


class TestDocumentPermission(TestCase):
    def test_authenticated_user_required(self):
        permission = DocumentPermission()

        # Anonymous user
        anonymous_user = Mock()
        anonymous_user.is_authenticated = False
        request = create_mock_request(anonymous_user)

        self.assertFalse(permission.has_permission(request, None))

        # Authenticated user
        user = UserFactory()
        request = create_mock_request(user)

        self.assertTrue(permission.has_permission(request, None))

    def test_superuser_access(self):
        permission = DocumentPermission()
        superuser = SuperuserFactory()
        document = DocumentFactory()

        # Test all methods for superuser
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(superuser, method)
            self.assertTrue(permission.has_object_permission(request, None, document))

    def test_owner_access(self):
        permission = DocumentPermission()
        owner = UserFactory()
        document = DocumentFactory(owner=owner)

        # Owner should have access to all operations
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(owner, method)
            self.assertTrue(permission.has_object_permission(request, None, document))

    def test_public_document_read_access(self):
        permission = DocumentPermission()
        user = UserFactory()
        public_document = DocumentFactory(is_public=True)

        # Any authenticated user should be able to read public documents
        for method in ["GET", "HEAD", "OPTIONS"]:
            request = create_mock_request(user, method)
            self.assertTrue(
                permission.has_object_permission(request, None, public_document),
            )

        # But not modify them
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(user, method)
            self.assertFalse(
                permission.has_object_permission(request, None, public_document),
            )

    def test_shared_document_access(self):
        permission = DocumentPermission()
        owner = UserFactory()
        shared_user = UserFactory()
        document = DocumentFactory(owner=owner, is_public=False)

        # Create a share
        ShareFactory(
            document=document,
            shared_with=shared_user,
            permission_level="view",
        )

        # Shared user should have read access
        for method in ["GET", "HEAD", "OPTIONS"]:
            request = create_mock_request(shared_user, method)
            self.assertTrue(permission.has_object_permission(request, None, document))

        # But not write access
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(shared_user, method)
            self.assertFalse(
                permission.has_object_permission(request, None, document),
            )

    def test_expired_share_no_access(self):
        permission = DocumentPermission()
        owner = UserFactory()
        shared_user = UserFactory()
        document = DocumentFactory(owner=owner, is_public=False)

        # Create an expired share
        ExpiredShareFactory(document=document, shared_with=shared_user)

        # Shared user should not have access to expired shares
        request = create_mock_request(shared_user, "GET")
        self.assertFalse(permission.has_object_permission(request, None, document))

    def test_non_shared_private_document_no_access(self):
        permission = DocumentPermission()
        owner = UserFactory()
        other_user = UserFactory()
        private_document = DocumentFactory(owner=owner, is_public=False)

        # Other user should not have access to private documents
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(other_user, method)
            self.assertFalse(
                permission.has_object_permission(request, None, private_document),
            )

    def test_delete_permission_always_denied(self):
        permission = DocumentPermission()
        user = UserFactory()
        document = DocumentFactory()

        # Even for non-owners, DELETE should be explicitly denied
        request = create_mock_request(user, "DELETE")
        self.assertFalse(permission.has_object_permission(request, None, document))


class TestSharePermission(TestCase):
    def test_authenticated_user_required(self):
        permission = SharePermission()

        # Anonymous user
        anonymous_user = Mock()
        anonymous_user.is_authenticated = False
        request = create_mock_request(anonymous_user)

        self.assertFalse(permission.has_permission(request, None))

        # Authenticated user
        user = UserFactory()
        request = create_mock_request(user)

        self.assertTrue(permission.has_permission(request, None))

    def test_superuser_access(self):
        permission = SharePermission()
        superuser = SuperuserFactory()
        share = ShareFactory()

        # Superuser should have access to all operations
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(superuser, method)
            self.assertTrue(permission.has_object_permission(request, None, share))

    def test_document_owner_access(self):
        permission = SharePermission()
        owner = UserFactory()
        shared_user = UserFactory()
        document = DocumentFactory(owner=owner)
        share = ShareFactory(
            document=document,
            shared_with=shared_user,
            shared_by=owner,
        )

        # Document owner should have full access to shares
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(owner, method)
            self.assertTrue(permission.has_object_permission(request, None, share))

    def test_share_creator_access(self):
        permission = SharePermission()
        owner = UserFactory()
        creator = UserFactory()
        shared_user = UserFactory()
        document = DocumentFactory(owner=owner)
        share = ShareFactory(
            document=document,
            shared_with=shared_user,
            shared_by=creator,
        )

        # Share creator should have full access
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(creator, method)
            self.assertTrue(permission.has_object_permission(request, None, share))

    def test_shared_with_user_read_access(self):
        permission = SharePermission()
        owner = UserFactory()
        shared_user = UserFactory()
        document = DocumentFactory(owner=owner)
        share = ShareFactory(
            document=document,
            shared_with=shared_user,
            shared_by=owner,
        )

        # User who is shared with should have read access
        for method in ["GET", "HEAD", "OPTIONS"]:
            request = create_mock_request(shared_user, method)
            self.assertTrue(permission.has_object_permission(request, None, share))

        # But not write access
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(shared_user, method)
            self.assertFalse(permission.has_object_permission(request, None, share))

    def test_unrelated_user_no_access(self):
        permission = SharePermission()
        owner = UserFactory()
        shared_user = UserFactory()
        unrelated_user = UserFactory()
        document = DocumentFactory(owner=owner)
        share = ShareFactory(
            document=document,
            shared_with=shared_user,
            shared_by=owner,
        )

        # Unrelated user should have no access
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(unrelated_user, method)
            self.assertFalse(permission.has_object_permission(request, None, share))


class TestCanShareDocument(TestCase):
    def test_superuser_can_share(self):
        permission = CanShareDocument()
        superuser = SuperuserFactory()
        document = DocumentFactory()

        request = create_mock_request(superuser)
        self.assertTrue(permission.has_object_permission(request, None, document))

    def test_owner_can_share(self):
        permission = CanShareDocument()
        owner = UserFactory()
        document = DocumentFactory(owner=owner)

        request = create_mock_request(owner)
        self.assertTrue(permission.has_object_permission(request, None, document))

    def test_non_owner_cannot_share(self):
        permission = CanShareDocument()
        owner = UserFactory()
        other_user = UserFactory()
        document = DocumentFactory(owner=owner)

        request = create_mock_request(other_user)
        self.assertFalse(permission.has_object_permission(request, None, document))

    def test_shared_user_cannot_share(self):
        permission = CanShareDocument()
        owner = UserFactory()
        shared_user = UserFactory()
        document = DocumentFactory(owner=owner)

        # Even if user has access to document through sharing, they cannot share it
        ShareFactory(
            document=document,
            shared_with=shared_user,
            permission_level="edit",
        )

        request = create_mock_request(shared_user)
        self.assertFalse(permission.has_object_permission(request, None, document))


class TestPermissionInteractions(TestCase):
    def test_multiple_shares_access(self):
        """Test access when user has multiple shares for the same document."""
        permission = DocumentPermission()
        owner = UserFactory()
        shared_user = UserFactory()
        document = DocumentFactory(owner=owner, is_public=False)

        # Create multiple shares (shouldn't happen in practice, but test robustness)
        ShareFactory(
            document=document,
            shared_with=shared_user,
            permission_level="view",
        )

        request = create_mock_request(shared_user, "GET")
        self.assertTrue(permission.has_object_permission(request, None, document))

    def test_permission_with_future_expiration(self):
        """Test that shares with future expiration work correctly."""
        permission = DocumentPermission()
        owner = UserFactory()
        shared_user = UserFactory()
        document = DocumentFactory(owner=owner, is_public=False)

        # Create share that expires in the future
        future_time = timezone.now() + timezone.timedelta(days=1)
        ShareFactory(
            document=document,
            shared_with=shared_user,
            expires_at=future_time,
        )

        request = create_mock_request(shared_user, "GET")
        self.assertTrue(permission.has_object_permission(request, None, document))

    def test_permission_edge_cases(self):
        """Test various edge cases in permission checking."""
        permission = DocumentPermission()
        user = UserFactory()
        document = DocumentFactory()

        # Test with unsupported HTTP methods
        for method in ["CONNECT", "TRACE", "CUSTOM"]:
            request = create_mock_request(user, method)
            # Should default to no access for unsupported methods
            self.assertFalse(permission.has_object_permission(request, None, document))

    def test_share_permission_edge_cases(self):
        """Test edge cases in share permissions."""
        permission = SharePermission()
        owner = UserFactory()
        document = DocumentFactory(owner=owner)

        # Test share where shared_by is None
        share = ShareFactory(document=document, shared_by=None)

        request = create_mock_request(owner, "GET")
        # Document owner should still have access even if shared_by is None
        self.assertTrue(permission.has_object_permission(request, None, share))

    def test_cascading_permissions(self):
        """Test that permissions work correctly in cascading scenarios."""
        doc_permission = DocumentPermission()
        share_permission = SharePermission()

        owner = UserFactory()
        user1 = UserFactory()
        user2 = UserFactory()

        document = DocumentFactory(owner=owner)

        # Owner shares with user1
        share1 = ShareFactory(document=document, shared_with=user1, shared_by=owner)

        # User1 tries to create another share (should not be allowed by CanShareDocument)
        can_share = CanShareDocument()
        request = create_mock_request(user1)
        self.assertFalse(can_share.has_object_permission(request, None, document))

        # But user1 can view the document
        request = create_mock_request(user1, "GET")
        self.assertTrue(doc_permission.has_object_permission(request, None, document))

        # And user1 can view their share
        request = create_mock_request(user1, "GET")
        self.assertTrue(share_permission.has_object_permission(request, None, share1))


class TestPermissionConsistency(TestCase):
    """Test that permissions are consistent across different scenarios."""

    def test_permission_consistency_across_methods(self):
        """Ensure permission logic is consistent across different HTTP methods."""
        permission = DocumentPermission()
        owner = UserFactory()
        user = UserFactory()

        # Test with public document
        public_doc = DocumentFactory(owner=owner, is_public=True)

        # Non-owner should have consistent read access
        for method in ["GET", "HEAD", "OPTIONS"]:
            request = create_mock_request(user, method)
            result = permission.has_object_permission(request, None, public_doc)
            self.assertTrue(
                result,
                f"Method {method} should allow access to public document",
            )

        # Non-owner should have consistent write denial
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(user, method)
            result = permission.has_object_permission(request, None, public_doc)
            self.assertFalse(
                result,
                f"Method {method} should deny access to public document",
            )

    def test_share_permission_consistency(self):
        """Ensure share permissions are consistent."""
        permission = SharePermission()
        owner = UserFactory()
        shared_user = UserFactory()
        other_user = UserFactory()

        document = DocumentFactory(owner=owner)
        share = ShareFactory(
            document=document,
            shared_with=shared_user,
            shared_by=owner,
        )

        # Shared user should consistently have read access
        for method in ["GET", "HEAD", "OPTIONS"]:
            request = create_mock_request(shared_user, method)
            result = permission.has_object_permission(request, None, share)
            self.assertTrue(result, f"Shared user should have {method} access")

        # Other user should consistently have no access
        for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
            request = create_mock_request(other_user, method)
            result = permission.has_object_permission(request, None, share)
            self.assertFalse(result, f"Other user should not have {method} access")
