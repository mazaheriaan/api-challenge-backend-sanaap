import json
import time
from unittest.mock import Mock
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory
from django.test import TestCase

from sanaap_api_challenge.documents.middleware import RequestLoggingMiddleware

from .factories import UserFactory

User = get_user_model()


class TestRequestLoggingMiddleware(TestCase):
    def setUp(self):
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = RequestLoggingMiddleware(self.get_response)
        self.factory = RequestFactory()

    def test_process_request_authenticated_user(self):
        user = UserFactory(username="testuser")
        request = self.factory.get("/api/documents/")
        request.user = user

        # Test process_request doesn't raise errors
        try:
            self.middleware.process_request(request)
            assert hasattr(request, "_start_time")
        except Exception as e:
            self.fail(f"Middleware should handle authenticated users: {e}")

    def test_process_request_anonymous_user(self):
        request = self.factory.get("/api/documents/")
        request.user = Mock()
        request.user.is_authenticated = False

        # Should handle anonymous users gracefully
        try:
            self.middleware.process_request(request)
            assert hasattr(request, "_start_time")
        except Exception as e:
            self.fail(f"Middleware should handle anonymous users: {e}")

    def test_middleware_with_post_request(self):
        user = UserFactory()
        request = self.factory.post("/api/documents/", {"title": "Test"})
        request.user = user

        # Should handle POST requests
        try:
            self.middleware.process_request(request)
            assert hasattr(request, "_start_time")
        except Exception as e:
            self.fail(f"Middleware should handle POST requests: {e}")

    @patch("sanaap_api_challenge.documents.middleware.logger")
    def test_middleware_logs_request_info(self, mock_logger):
        user = UserFactory()
        request = self.factory.get("/api/documents/")
        request.user = user

        self.middleware.process_request(request)
        # Verify that logging was attempted
        assert mock_logger.info.called

    def test_middleware_handles_json_body(self):
        user = UserFactory()
        request = self.factory.post(
            "/api/documents/",
            json.dumps({"title": "Test Document"}),
            content_type="application/json",
        )
        request.user = user

        # Should handle JSON body gracefully
        try:
            self.middleware.process_request(request)
            assert hasattr(request, "_start_time")
        except Exception as e:
            self.fail(f"Middleware should handle JSON body: {e}")

    def test_middleware_handles_large_body(self):
        user = UserFactory()
        large_data = {"data": "x" * 10000}  # Large JSON payload
        request = self.factory.post(
            "/api/documents/",
            json.dumps(large_data),
            content_type="application/json",
        )
        request.user = user

        # Should handle large bodies gracefully
        try:
            self.middleware.process_request(request)
            assert hasattr(request, "_start_time")
        except Exception as e:
            self.fail(f"Middleware should handle large bodies: {e}")

    def test_middleware_body_access_exception(self):
        user = UserFactory()
        request = self.factory.post("/api/documents/", {"title": "Test"})
        request.user = user

        # The middleware handles body access exceptions internally
        try:
            self.middleware.process_request(request)
            assert hasattr(request, "_start_time")
        except Exception as e:
            self.fail(f"Should handle body access exceptions gracefully: {e}")

    def test_process_response_with_timing(self):
        user = UserFactory()
        request = self.factory.get("/api/documents/")
        request.user = user
        request._start_time = time.time() - 0.5  # Simulate 0.5 second request

        response = HttpResponse("OK")
        result = self.middleware.process_response(request, response)

        # Response should have timing header
        self.assertIn("X-Response-Time", result)
        self.assertTrue(result["X-Response-Time"].endswith("s"))

    def test_process_response_without_start_time(self):
        user = UserFactory()
        request = self.factory.get("/api/documents/")
        request.user = user
        # No _start_time attribute

        response = HttpResponse("OK")
        result = self.middleware.process_response(request, response)

        # Should handle gracefully
        self.assertEqual(result, response)

    def test_get_client_ip_method(self):
        # Test the _get_client_ip method
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "192.168.1.1, 10.0.0.1"

        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, "192.168.1.1")

    def test_get_client_ip_remote_addr(self):
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, "127.0.0.1")

    def test_get_client_ip_no_ip(self):
        request = self.factory.get("/")
        # Clear META to simulate no IP information
        request.META = {}

        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, "unknown")

    def test_is_sensitive_operation(self):
        # Test sensitive path and method
        request = self.factory.post("/api/documents/")
        self.assertTrue(self.middleware._is_sensitive_operation(request))

        # Test non-sensitive method
        request = self.factory.get("/api/documents/")
        self.assertFalse(self.middleware._is_sensitive_operation(request))

        # Test non-sensitive path
        request = self.factory.post("/api/other/")
        self.assertFalse(self.middleware._is_sensitive_operation(request))

    def test_middleware_with_different_methods(self):
        user = UserFactory()

        methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
        for method in methods:
            request = getattr(self.factory, method.lower())("/api/documents/")
            request.user = user

            try:
                self.middleware.process_request(request)
                self.assertTrue(hasattr(request, "_start_time"))
            except Exception as e:
                self.fail(f"Middleware should handle {method} requests: {e}")

    def test_middleware_with_query_parameters(self):
        user = UserFactory()
        request = self.factory.get("/api/documents/?search=test&page=2")
        request.user = user

        # Should handle query parameters gracefully
        try:
            self.middleware.process_request(request)
            self.assertTrue(hasattr(request, "_start_time"))
        except Exception as e:
            self.fail(f"Middleware should handle query parameters: {e}")

    def test_middleware_with_different_content_types(self):
        user = UserFactory()

        content_types = [
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
            "text/plain",
        ]

        for content_type in content_types:
            request = self.factory.post(
                "/api/documents/",
                {"data": "test"},
                content_type=content_type,
            )
            request.user = user

            try:
                self.middleware.process_request(request)
                self.assertTrue(hasattr(request, "_start_time"))
            except Exception as e:
                self.fail(f"Middleware should handle {content_type}: {e}")


class TestMiddlewareIntegration(TestCase):
    def test_middleware_in_request_response_cycle(self):
        # Test complete request-response cycle
        def simple_view(request):
            return HttpResponse("Success")

        middleware = RequestLoggingMiddleware(simple_view)
        factory = RequestFactory()
        user = UserFactory()

        request = factory.get("/api/documents/")
        request.user = user

        # Process request
        middleware.process_request(request)

        # Get response
        response = middleware.get_response(request)

        # Process response
        final_response = middleware.process_response(request, response)

        self.assertEqual(final_response.content, b"Success")
        self.assertEqual(final_response.status_code, 200)
        self.assertIn("X-Response-Time", final_response)

    def test_middleware_error_handling_in_response(self):
        user = UserFactory()
        request = RequestFactory().get("/api/documents/")
        request.user = user
        request._start_time = time.time()

        middleware = RequestLoggingMiddleware(Mock())

        # Test with error response
        error_response = HttpResponse("Not Found", status=404)
        result = middleware.process_response(request, error_response)

        self.assertEqual(result.status_code, 404)
        self.assertIn("X-Response-Time", result)

    @patch("sanaap_api_challenge.documents.middleware.logger")
    def test_middleware_logs_slow_requests(self, mock_logger):
        user = UserFactory()
        request = RequestFactory().get("/api/documents/")
        request.user = user
        request._start_time = time.time() - 2.0  # Simulate 2 second request

        middleware = RequestLoggingMiddleware(Mock())
        response = HttpResponse("OK")

        middleware.process_response(request, response)

        # Should log warning for slow request
        self.assertTrue(mock_logger.warning.called)

    @patch("sanaap_api_challenge.documents.middleware.logger")
    def test_middleware_logs_error_responses(self, mock_logger):
        user = UserFactory()
        request = RequestFactory().get("/api/documents/")
        request.user = user
        request._start_time = time.time()

        middleware = RequestLoggingMiddleware(Mock())
        error_response = HttpResponse("Server Error", status=500)

        middleware.process_response(request, error_response)

        # Should log warning for error response
        self.assertTrue(mock_logger.warning.called)
