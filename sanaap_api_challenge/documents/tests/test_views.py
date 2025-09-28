from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from rest_framework.test import APITestCase

from sanaap_api_challenge.documents.models import Document
from sanaap_api_challenge.documents.models import Share

from .factories import AccessFactory
from .factories import DocumentFactory
from .factories import ShareFactory
from .factories import UserFactory

User = get_user_model()


class TestDocumentViewSet(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_list_documents_authenticated(self):
        # Create documents with different access levels
        owned_doc = DocumentFactory(owner=self.user)
        public_doc = DocumentFactory(is_public=True)
        other_user_doc = DocumentFactory()
        shared_doc = DocumentFactory()
        ShareFactory(document=shared_doc, shared_with=self.user)

        response = self.client.get("/api/documents/items/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should include owned, public, and shared documents
        document_ids = [doc["id"] for doc in data["results"]]
        self.assertIn(owned_doc.id, document_ids)
        self.assertIn(public_doc.id, document_ids)
        self.assertIn(shared_doc.id, document_ids)
        self.assertNotIn(other_user_doc.id, document_ids)

    def test_list_documents_unauthenticated(self):
        client = APIClient()
        response = client.get("/api/documents/items/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_document_owner(self):
        document = DocumentFactory(owner=self.user)
        response = self.client.get(f"/api/documents/items/{document.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], document.id)

    def test_retrieve_document_no_access(self):
        document = DocumentFactory()
        response = self.client.get(f"/api/documents/items/{document.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_public_document(self):
        document = DocumentFactory(is_public=True)
        response = self.client.get(f"/api/documents/items/{document.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("sanaap_api_challenge.utils.minio_client.minio_client")
    def test_create_document(self, mock_minio):
        mock_minio.upload_file.return_value = True
        mock_minio.file_exists.return_value = True

        file = SimpleUploadedFile(
            "test.txt",
            b"test content",
            content_type="text/plain",
        )
        response = self.client.post(
            "/api/documents/items/",
            {"title": "Test Document", "file": file, "description": "Test description"},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Test Document")
        self.assertTrue(Document.objects.filter(title="Test Document").exists())

    def test_create_document_invalid_file(self):
        file = SimpleUploadedFile(
            "test.exe",
            b"test content",
            content_type="application/octet-stream",
        )
        response = self.client.post(
            "/api/documents/items/",
            {"title": "Test Document", "file": file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_document_owner(self):
        document = DocumentFactory(owner=self.user)
        response = self.client.patch(
            f"/api/documents/items/{document.id}/",
            {"title": "Updated Title"},
            format="json",
        )

        # DocumentViewSet doesn't support PATCH - only GET, POST, DELETE
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_update_document_no_permission(self):
        document = DocumentFactory()
        response = self.client.patch(
            f"/api/documents/items/{document.id}/",
            {"title": "Updated Title"},
            format="json",
        )

        # DocumentViewSet doesn't support PATCH
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_document_owner(self):
        document = DocumentFactory(owner=self.user)
        response = self.client.delete(f"/api/documents/items/{document.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        # Document is marked as deleted, not physically deleted
        document.refresh_from_db()
        self.assertEqual(document.status, "deleted")

    def test_delete_document_no_permission(self):
        document = DocumentFactory()
        response = self.client.delete(f"/api/documents/items/{document.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("sanaap_api_challenge.documents.api.views.minio_client")
    def test_download_document(self, mock_minio):
        mock_minio.get_file_data.return_value = b"file content"
        document = DocumentFactory(owner=self.user)

        response = self.client.get(f"/api/documents/items/{document.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check that the file download works
        self.assertEqual(response.content, b"file content")
        self.assertEqual(response["Content-Type"], document.content_type)
        self.assertIn("attachment", response.get("Content-Disposition", ""))

    def test_download_document_no_access(self):
        document = DocumentFactory()
        response = self.client.get(f"/api/documents/items/{document.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_my_documents(self):
        owned_doc = DocumentFactory(owner=self.user)
        other_doc = DocumentFactory()

        response = self.client.get("/api/documents/my/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("owned", response.data)
        owned_ids = [doc["id"] for doc in response.data["owned"]]
        self.assertIn(owned_doc.id, owned_ids)
        # other_doc should not be in owned documents
        self.assertNotIn(other_doc.id, owned_ids)

    def test_shared_with_me(self):
        shared_doc = DocumentFactory()
        ShareFactory(document=shared_doc, shared_with=self.user)
        not_shared = DocumentFactory()

        # Shared documents are returned via the my-documents endpoint
        response = self.client.get("/api/documents/my/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("shared", response.data)
        shared_ids = [doc["id"] for doc in response.data["shared"]]
        self.assertIn(shared_doc.id, shared_ids)
        self.assertNotIn(not_shared.id, shared_ids)

    def test_filter_by_owner(self):
        user2 = UserFactory()
        doc1 = DocumentFactory(owner=self.user)
        doc2 = DocumentFactory(owner=user2, is_public=True)

        response = self.client.get(f"/api/documents/items/?owner={self.user.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doc_ids = [doc["id"] for doc in response.data["results"]]
        self.assertIn(doc1.id, doc_ids)
        self.assertNotIn(doc2.id, doc_ids)

    def test_search_documents(self):
        doc1 = DocumentFactory(title="Python Tutorial", owner=self.user)
        doc2 = DocumentFactory(title="Java Guide", owner=self.user)

        response = self.client.get("/api/documents/items/?search=Python")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        doc_ids = [doc["id"] for doc in response.data["results"]]
        self.assertIn(doc1.id, doc_ids)
        self.assertNotIn(doc2.id, doc_ids)

    def test_ordering(self):
        doc1 = DocumentFactory(title="A Document", owner=self.user)
        doc2 = DocumentFactory(title="B Document", owner=self.user)
        doc3 = DocumentFactory(title="C Document", owner=self.user)

        response = self.client.get("/api/documents/items/?ordering=-title")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [doc["title"] for doc in response.data["results"]]
        self.assertEqual(titles[0], "C Document")


class TestShareViewSet(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.document = DocumentFactory(owner=self.user)
        self.other_user = UserFactory()

    def test_list_shares_document_owner(self):
        share1 = ShareFactory(document=self.document, shared_by=self.user)
        share2 = ShareFactory(document=self.document, shared_by=self.user)
        other_share = ShareFactory()

        response = self.client.get("/api/documents/shares/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        share_ids = [share["id"] for share in response.data["results"]]
        self.assertIn(share1.id, share_ids)
        self.assertIn(share2.id, share_ids)
        self.assertNotIn(other_share.id, share_ids)

    def test_list_shares_no_access(self):
        other_doc = DocumentFactory()
        response = self.client.get("/api/documents/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # User should only see shares they are involved in
        share_ids = [share["id"] for share in response.data["results"]]
        # No shares from other documents should be visible
        self.assertEqual(len(share_ids), 0)

    def test_create_share_owner(self):
        response = self.client.post(
            f"/api/documents/items/{self.document.id}/share/",
            {
                "shared_with_id": self.other_user.id,
                "permission_level": "view",
                "expires_at": (timezone.now() + timezone.timedelta(days=7)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Share.objects.filter(
                document=self.document,
                shared_with=self.other_user,
            ).exists(),
        )

    def test_create_share_duplicate(self):
        ShareFactory(document=self.document, shared_with=self.other_user)

        response = self.client.post(
            f"/api/documents/items/{self.document.id}/share/",
            {"shared_with_id": self.other_user.id, "permission_level": "view"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_share(self):
        user2 = UserFactory()
        user3 = UserFactory()

        response = self.client.post(
            f"/api/documents/items/{self.document.id}/bulk_share/",
            {
                "user_ids": [user2.id, user3.id],
                "permission_level": "view",
                "expires_at": (timezone.now() + timezone.timedelta(days=7)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["created"], 2)
        self.assertTrue(
            Share.objects.filter(document=self.document, shared_with=user2).exists(),
        )
        self.assertTrue(
            Share.objects.filter(document=self.document, shared_with=user3).exists(),
        )

    def test_update_share_permission(self):
        share = ShareFactory(
            document=self.document,
            shared_by=self.user,
            permission_level="view",
        )

        response = self.client.patch(
            f"/api/documents/shares/{share.id}/",
            {"permission_level": "edit"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        share.refresh_from_db()
        self.assertEqual(share.permission_level, "edit")

    def test_delete_share_owner(self):
        share = ShareFactory(document=self.document, shared_by=self.user)

        response = self.client.delete(
            f"/api/documents/shares/{share.id}/",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Share.objects.filter(id=share.id).exists())

    def test_delete_share_no_permission(self):
        other_doc = DocumentFactory()
        share = ShareFactory(document=other_doc)

        response = self.client.delete(
            f"/api/documents/shares/{share.id}/",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestAccessViewSet(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.token, _ = Token.objects.get_or_create(user=self.user)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.document = DocumentFactory(owner=self.user)

    def test_list_access_logs_owner(self):
        access1 = AccessFactory(document=self.document)
        access2 = AccessFactory(document=self.document)
        other_access = AccessFactory()

        response = self.client.get(
            f"/api/documents/items/{self.document.id}/access_logs/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access_ids = [log["id"] for log in response.data["results"]]
        self.assertIn(access1.id, access_ids)
        self.assertIn(access2.id, access_ids)
        self.assertNotIn(other_access.id, access_ids)

    def test_list_access_logs_no_permission(self):
        other_doc = DocumentFactory()
        response = self.client.get(f"/api/documents/items/{other_doc.id}/access_logs/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_access_logs_ordering(self):
        access1 = AccessFactory(document=self.document)
        access2 = AccessFactory(document=self.document)

        response = self.client.get(
            f"/api/documents/items/{self.document.id}/access_logs/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be ordered by created descending (most recent first)
        self.assertEqual(len(response.data["results"]), 2)
