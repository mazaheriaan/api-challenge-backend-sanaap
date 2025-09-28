#!/usr/bin/env python3
"""
Simple HTTP server to serve the upload_monitor.html file and proxy API requests.
This avoids CORS issues when testing locally.

Usage:
    python serve_upload_monitor.py

Then open: http://localhost:8080/
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import json
from http import HTTPStatus

API_BASE_URL = "http://localhost:8000"
SERVER_PORT = 8080


class ProxyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with API proxy support."""

    def end_headers(self):
        # Add CORS headers for local development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-CSRFToken')
        super().end_headers()

    def do_OPTIONS(self):
        """Handle preflight CORS requests."""
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        """Serve HTML file or proxy API requests."""
        try:
            if self.path == '/' or self.path == '/index.html':
                self.path = '/upload_monitor.html'

            if self.path.startswith('/api/'):
                self.proxy_request('GET')
            else:
                super().do_GET()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Client disconnected, ignore
            pass
        except Exception as e:
            print(f"Error in do_GET: {e}")
            try:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
            except:
                pass

    def do_POST(self):
        """Proxy POST requests to API."""
        try:
            if self.path.startswith('/api/'):
                self.proxy_request('POST')
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            print(f"Error in do_POST: {e}")
            try:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
            except:
                pass

    def do_PUT(self):
        """Proxy PUT requests to API."""
        try:
            if self.path.startswith('/api/'):
                self.proxy_request('PUT')
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            print(f"Error in do_PUT: {e}")
            try:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
            except:
                pass

    def do_DELETE(self):
        """Proxy DELETE requests to API."""
        try:
            if self.path.startswith('/api/'):
                self.proxy_request('DELETE')
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:
            print(f"Error in do_DELETE: {e}")
            try:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)
            except:
                pass

    def proxy_request(self, method):
        """Proxy request to the API server."""
        try:
            # Build target URL
            url = f"{API_BASE_URL}{self.path}"

            # Get request body if present
            content_length = self.headers.get('Content-Length')
            body = None
            if content_length:
                body = self.rfile.read(int(content_length))

            # Create request with same headers
            req = urllib.request.Request(url, data=body, method=method)

            # Copy relevant headers
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'connection']:
                    req.add_header(header, value)

            # Make request to API
            response = urllib.request.urlopen(req)

            # Send response back to client
            self.send_response(response.getcode())

            # Copy response headers
            for header, value in response.headers.items():
                if header.lower() not in ['connection', 'transfer-encoding']:
                    self.send_header(header, value)
            self.end_headers()

            # Copy response body
            try:
                self.wfile.write(response.read())
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # Client disconnected while sending response
                pass

        except urllib.error.HTTPError as e:
            try:
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(e.read())
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Client disconnected, don't log these as errors
            pass
        except Exception as e:
            try:
                self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass


def run_server():
    """Run the proxy server."""
    with socketserver.TCPServer(("", SERVER_PORT), ProxyHTTPRequestHandler) as httpd:
        print(f"🚀 Server running at http://localhost:{SERVER_PORT}/")
        print(f"📡 Proxying API requests to {API_BASE_URL}")
        print("Press Ctrl+C to stop")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Server stopped")


if __name__ == "__main__":
    run_server()