from urllib.parse import urlencode

from django.conf import settings


def get_upload_status_websocket_url(document_id, request=None):
    if request:
        scheme = "wss" if request.is_secure() else "ws"
        host = request.get_host()
        ws_url = f"{scheme}://{host}/ws/upload/{document_id}/"
    else:
        # Fallback to settings-based URL construction
        scheme = "wss" if getattr(settings, "USE_TLS", False) else "ws"
        host = getattr(settings, "ALLOWED_HOSTS", ["localhost"])[0]
        if host == "*":
            host = "localhost:8000"  # Development fallback
        ws_url = f"{scheme}://{host}/ws/upload/{document_id}/"

    return ws_url


def get_upload_status_websocket_url_with_auth(
    document_id,
    user_token=None,
    request=None,
):
    """
    Generate WebSocket URL with authentication parameters.

    Args:
        document_id: ID of the document to track
        user_token: Authentication token (optional)
        request: HTTP request object (optional)

    Returns:
        str: WebSocket URL with authentication parameters
    """
    base_url = get_upload_status_websocket_url(document_id, request)

    # Add authentication parameters if provided
    params = {}
    if user_token:
        params["token"] = user_token

    if params:
        separator = "?" if "?" not in base_url else "&"
        base_url += separator + urlencode(params)

    return base_url


class UploadStatusManager:
    """
    Helper class for managing upload status tracking on the frontend.

    This class provides methods that can be easily translated to JavaScript
    for frontend WebSocket connection management.
    """

    @staticmethod
    def get_connection_config(document_id, request=None):
        """
        Get WebSocket connection configuration for frontend.

        Args:
            document_id: ID of the document to track
            request: HTTP request object (optional)

        Returns:
            dict: Configuration object for WebSocket connection
        """
        return {
            "url": get_upload_status_websocket_url(document_id, request),
            "document_id": document_id,
            "reconnect": True,
            "max_reconnect_attempts": 5,
            "reconnect_delay": 1000,  # milliseconds
            "ping_interval": 30000,  # milliseconds
        }

    @staticmethod
    def get_message_handlers():
        """
        Get recommended message handlers for frontend WebSocket implementation.

        Returns:
            dict: Dictionary of message types and their descriptions
        """
        return {
            "current_status": {
                "description": "Initial status when connecting",
                "fields": [
                    "document_id",
                    "status",
                    "progress",
                    "error_message",
                    "task_id",
                    "timestamp",
                ],
            },
            "upload_status": {
                "description": "General status update",
                "fields": [
                    "document_id",
                    "status",
                    "progress",
                    "error_message",
                    "timestamp",
                ],
            },
            "upload_progress": {
                "description": "Progress update during upload",
                "fields": ["document_id", "progress", "timestamp"],
            },
            "upload_completed": {
                "description": "Upload completed successfully",
                "fields": ["document_id", "status", "message", "timestamp"],
            },
            "upload_failed": {
                "description": "Upload failed with error",
                "fields": ["document_id", "status", "error_message", "timestamp"],
            },
            "pong": {
                "description": "Response to ping for connection health check",
                "fields": ["timestamp"],
            },
        }

    @staticmethod
    def get_client_messages():
        """
        Get client messages that can be sent to the WebSocket.

        Returns:
            dict: Dictionary of client message types and their descriptions
        """
        return {
            "ping": {
                "description": "Health check message",
                "example": {"type": "ping"},
            },
            "get_status": {
                "description": "Request current upload status",
                "example": {"type": "get_status"},
            },
        }


def generate_frontend_websocket_example(document_id, request=None):
    """
    Generate JavaScript example code for WebSocket connection.

    Args:
        document_id: ID of the document to track
        request: HTTP request object (optional)

    Returns:
        str: JavaScript code example
    """
    config = UploadStatusManager.get_connection_config(document_id, request)

    js_code = f"""
// WebSocket connection for upload status tracking
class UploadStatusTracker {{
    constructor(documentId) {{
        this.documentId = documentId;
        this.config = {config};
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
    }}

    connect() {{
        try {{
            this.websocket = new WebSocket(this.config.url);
            this.setupEventHandlers();
        }} catch (error) {{
            console.error('Failed to create WebSocket connection:', error);
            this.handleReconnect();
        }}
    }}

    setupEventHandlers() {{
        this.websocket.onopen = (event) => {{
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.startPingInterval();
        }};

        this.websocket.onmessage = (event) => {{
            try {{
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            }} catch (error) {{
                console.error('Failed to parse WebSocket message:', error);
            }}
        }};

        this.websocket.onclose = (event) => {{
            console.log('WebSocket closed:', event.code, event.reason);
            this.stopPingInterval();
            if (this.config.reconnect && event.code !== 1000) {{
                this.handleReconnect();
            }}
        }};

        this.websocket.onerror = (error) => {{
            console.error('WebSocket error:', error);
        }};
    }}

    handleMessage(data) {{
        switch (data.type) {{
            case 'current_status':
                this.onStatusUpdate(data);
                break;
            case 'upload_status':
                this.onStatusUpdate(data);
                break;
            case 'upload_progress':
                this.onProgressUpdate(data);
                break;
            case 'upload_completed':
                this.onUploadCompleted(data);
                break;
            case 'upload_failed':
                this.onUploadFailed(data);
                break;
            case 'pong':
                // Connection health check response
                break;
            default:
                console.warn('Unknown message type:', data.type);
        }}
    }}

    onStatusUpdate(data) {{
        // Update UI with status
        console.log('Status update:', data.status, data.progress);
    }}

    onProgressUpdate(data) {{
        // Update progress bar
        console.log('Progress update:', data.progress);
    }}

    onUploadCompleted(data) {{
        // Handle successful upload
        console.log('Upload completed:', data.message);
    }}

    onUploadFailed(data) {{
        // Handle upload failure
        console.error('Upload failed:', data.error_message);
    }}

    sendMessage(message) {{
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {{
            this.websocket.send(JSON.stringify(message));
        }}
    }}

    ping() {{
        this.sendMessage({{ type: 'ping' }});
    }}

    requestStatus() {{
        this.sendMessage({{ type: 'get_status' }});
    }}

    startPingInterval() {{
        this.pingInterval = setInterval(() => {{
            this.ping();
        }}, this.config.ping_interval);
    }}

    stopPingInterval() {{
        if (this.pingInterval) {{
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }}
    }}

    handleReconnect() {{
        if (this.reconnectAttempts < this.config.max_reconnect_attempts) {{
            this.reconnectAttempts++;
            const delay = this.config.reconnect_delay * this.reconnectAttempts;
            console.log(`Reconnecting in ${{delay}}ms (attempt ${{this.reconnectAttempts}})`);

            this.reconnectTimer = setTimeout(() => {{
                this.connect();
            }}, delay);
        }} else {{
            console.error('Max reconnection attempts reached');
        }}
    }}

    disconnect() {{
        this.config.reconnect = false;
        this.stopPingInterval();
        if (this.reconnectTimer) {{
            clearTimeout(this.reconnectTimer);
        }}
        if (this.websocket) {{
            this.websocket.close(1000, 'Client disconnecting');
        }}
    }}
}}

// Usage example:
const tracker = new UploadStatusTracker({document_id});
tracker.connect();

// Don't forget to disconnect when done
// tracker.disconnect();
"""

    return js_code.strip()


def get_upload_status_response_format():
    """
    Get the expected response format for upload status updates.

    Returns:
        dict: Example response formats for different message types
    """
    return {
        "current_status": {
            "type": "current_status",
            "document_id": 123,
            "status": "processing",
            "progress": {
                "step": "uploading_to_storage",
                "progress": 50,
            },
            "error_message": "",
            "task_id": "celery-task-id",
            "timestamp": "2023-01-01T12:00:00.000Z",
        },
        "upload_progress": {
            "type": "upload_progress",
            "document_id": 123,
            "progress": {
                "step": "finalizing",
                "progress": 90,
            },
            "timestamp": "2023-01-01T12:01:00.000Z",
        },
        "upload_completed": {
            "type": "upload_completed",
            "document_id": 123,
            "status": "completed",
            "message": "Upload completed successfully",
            "timestamp": "2023-01-01T12:02:00.000Z",
        },
        "upload_failed": {
            "type": "upload_failed",
            "document_id": 123,
            "status": "failed",
            "error_message": "File validation failed",
            "timestamp": "2023-01-01T12:02:00.000Z",
        },
    }
