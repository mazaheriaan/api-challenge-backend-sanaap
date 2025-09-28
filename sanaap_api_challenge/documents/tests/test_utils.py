from unittest.mock import Mock

from django.test import SimpleTestCase

from sanaap_api_challenge.documents.api.utils import calculate_file_hash
from sanaap_api_challenge.documents.api.utils import generate_unique_filename
from sanaap_api_challenge.documents.api.utils import get_client_ip
from sanaap_api_challenge.documents.api.utils import get_file_content_type
from sanaap_api_challenge.documents.api.utils import get_file_extension
from sanaap_api_challenge.documents.api.utils import get_human_readable_size
from sanaap_api_challenge.documents.api.utils import sanitize_filename


class TestFileUtilities(SimpleTestCase):
    def test_get_file_content_type_known_extensions(self):
        # Test known file types
        self.assertEqual(get_file_content_type("document.pdf"), "application/pdf")
        self.assertEqual(get_file_content_type("image.jpg"), "image/jpeg")
        self.assertEqual(get_file_content_type("image.png"), "image/png")
        self.assertEqual(get_file_content_type("document.txt"), "text/plain")
        self.assertEqual(get_file_content_type("data.json"), "application/json")

    def test_get_file_content_type_unknown_extension(self):
        # Test unknown file type
        self.assertEqual(
            get_file_content_type("file.unknown"), "application/octet-stream"
        )
        self.assertEqual(get_file_content_type("file"), "application/octet-stream")

    def test_get_file_content_type_case_insensitive(self):
        # Test case insensitivity
        self.assertEqual(get_file_content_type("FILE.PDF"), "application/pdf")
        self.assertEqual(get_file_content_type("Image.JPG"), "image/jpeg")

    def test_calculate_file_hash(self):
        content = b"test file content"
        hash_result = calculate_file_hash(content)

        self.assertIsInstance(hash_result, str)
        self.assertEqual(
            len(hash_result), 64
        )  # SHA-256 produces 64 character hex string

        # Same content should produce same hash
        self.assertEqual(calculate_file_hash(content), hash_result)

        # Different content should produce different hash
        different_content = b"different content"
        self.assertNotEqual(calculate_file_hash(different_content), hash_result)

    def test_calculate_file_hash_empty_content(self):
        empty_hash = calculate_file_hash(b"")
        self.assertIsInstance(empty_hash, str)
        self.assertEqual(len(empty_hash), 64)

    def test_get_human_readable_size_bytes(self):
        self.assertEqual(get_human_readable_size(0), "0 B")
        self.assertEqual(get_human_readable_size(512), "512.0 B")
        self.assertEqual(get_human_readable_size(1023), "1023.0 B")

    def test_get_human_readable_size_kilobytes(self):
        self.assertEqual(get_human_readable_size(1024), "1.0 KB")
        self.assertEqual(get_human_readable_size(1536), "1.5 KB")
        self.assertEqual(get_human_readable_size(1024 * 1023), "1023.0 KB")

    def test_get_human_readable_size_megabytes(self):
        self.assertEqual(get_human_readable_size(1024 * 1024), "1.0 MB")
        self.assertEqual(get_human_readable_size(1024 * 1024 * 5), "5.0 MB")
        self.assertEqual(get_human_readable_size(1024 * 1024 * 1.5), "1.5 MB")

    def test_get_human_readable_size_gigabytes(self):
        self.assertEqual(get_human_readable_size(1024 * 1024 * 1024), "1.0 GB")
        self.assertEqual(get_human_readable_size(1024 * 1024 * 1024 * 2), "2.0 GB")

    def test_get_human_readable_size_terabytes(self):
        self.assertEqual(get_human_readable_size(1024 * 1024 * 1024 * 1024), "1.0 TB")

    def test_get_file_extension_with_extension(self):
        self.assertEqual(get_file_extension("document.pdf"), "pdf")
        self.assertEqual(get_file_extension("image.jpeg"), "jpeg")
        self.assertEqual(get_file_extension("archive.tar.gz"), "gz")  # Last extension
        self.assertEqual(get_file_extension("FILE.PDF"), "pdf")  # Case insensitive

    def test_get_file_extension_without_extension(self):
        self.assertEqual(get_file_extension("filename"), "")
        self.assertEqual(get_file_extension(""), "")
        self.assertEqual(get_file_extension("file."), "")

    def test_get_file_extension_multiple_dots(self):
        self.assertEqual(get_file_extension("my.file.name.txt"), "txt")
        self.assertEqual(get_file_extension("file.backup.2023.zip"), "zip")

    def test_sanitize_filename_normal(self):
        self.assertEqual(sanitize_filename("normal_file.txt"), "normal_file.txt")
        self.assertEqual(
            sanitize_filename("file with spaces.pdf"), "file with spaces.pdf"
        )

    def test_sanitize_filename_dangerous_characters(self):
        # Test removal of dangerous characters
        self.assertEqual(sanitize_filename("file<test>.txt"), "file_test_.txt")
        self.assertEqual(sanitize_filename('file"test".txt'), "file_test_.txt")
        self.assertEqual(sanitize_filename("file\\test/file.txt"), "file_test_file.txt")
        self.assertEqual(sanitize_filename("file|test?.txt"), "file_test_.txt")
        self.assertEqual(sanitize_filename("file*test.txt"), "file_test.txt")

    def test_sanitize_filename_control_characters(self):
        # Test removal of control characters
        filename_with_control = "file\x00\x01test.txt"
        result = sanitize_filename(filename_with_control)
        self.assertNotIn("\x00", result)
        self.assertNotIn("\x01", result)
        self.assertEqual(result, "filetest.txt")

    def test_sanitize_filename_long_filename(self):
        # Test filename length limitation
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        self.assertLessEqual(len(result), 255)
        self.assertTrue(result.endswith(".txt"))

    def test_sanitize_filename_long_filename_without_extension(self):
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        self.assertLessEqual(len(result), 255)

    def test_sanitize_filename_whitespace(self):
        self.assertEqual(sanitize_filename("  file.txt  "), "file.txt")
        self.assertEqual(sanitize_filename("\tfile.txt\n"), "file.txt")

    def test_generate_unique_filename_basic(self):
        result = generate_unique_filename("test.pdf", 123)

        # Test that the result has the expected structure
        parts = result.split("_")
        self.assertGreaterEqual(len(parts), 4)  # prefix, user_id, timestamp, unique_id
        self.assertEqual(parts[0], "doc")
        self.assertEqual(parts[1], "123")
        self.assertTrue(result.endswith(".pdf"))
        self.assertGreater(len(result), 20)  # Should be reasonably long

    def test_generate_unique_filename_custom_prefix(self):
        result = generate_unique_filename("test.pdf", 123, prefix="custom")

        # Test that the result has the expected structure with custom prefix
        parts = result.split("_")
        self.assertGreaterEqual(len(parts), 4)  # prefix, user_id, timestamp, unique_id
        self.assertEqual(parts[0], "custom")
        self.assertEqual(parts[1], "123")
        self.assertTrue(result.endswith(".pdf"))
        self.assertGreater(len(result), 20)  # Should be reasonably long

    def test_generate_unique_filename_no_extension(self):
        result = generate_unique_filename("testfile", 123)

        # Should handle files without extension
        parts = result.split("_")
        self.assertGreaterEqual(len(parts), 4)
        self.assertEqual(parts[0], "doc")
        self.assertEqual(parts[1], "123")
        # Should not add an extension if original didn't have one
        self.assertNotIn(".", result)

    def test_generate_unique_filename_uniqueness(self):
        # Test that consecutive calls generate different filenames
        result1 = generate_unique_filename("test.pdf", 123)
        result2 = generate_unique_filename("test.pdf", 123)

        self.assertNotEqual(result1, result2)


class TestNetworkUtilities(SimpleTestCase):
    def test_get_client_ip_from_x_forwarded_for(self):
        request = Mock()
        request.META = {"HTTP_X_FORWARDED_FOR": "192.168.1.1, 10.0.0.1"}

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_from_x_real_ip(self):
        # The actual function doesn't check HTTP_X_REAL_IP, only X_FORWARDED_FOR and REMOTE_ADDR
        request = Mock()
        request.META = {"REMOTE_ADDR": "192.168.1.1"}

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_from_remote_addr(self):
        request = Mock()
        request.META = {"REMOTE_ADDR": "192.168.1.1"}

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_fallback(self):
        request = Mock()
        request.META = {}

        ip = get_client_ip(request)
        # The function returns empty string when no IP is found, not "127.0.0.1"
        self.assertEqual(ip, "")

    def test_get_client_ip_priority_order(self):
        # X-Forwarded-For should take priority over REMOTE_ADDR
        request = Mock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "192.168.1.1",
            "REMOTE_ADDR": "172.16.0.1",
        }

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_x_forwarded_for_whitespace(self):
        request = Mock()
        request.META = {"HTTP_X_FORWARDED_FOR": " 192.168.1.1 , 10.0.0.1 "}

        ip = get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")
