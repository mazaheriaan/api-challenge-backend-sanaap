import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from .models import Document

User = get_user_model()
logger = logging.getLogger(__name__)


class UploadStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.document_id = self.scope["url_route"]["kwargs"]["document_id"]
        self.group_name = f"upload_{self.document_id}"
        self.user = self.scope.get("user")

        if not self.user or not self.user.is_authenticated:
            logger.warning(
                "Unauthenticated user attempted to connect to upload status for document %s",
                self.document_id,
            )
            await self.close(code=4001)
            return

        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)

            await self.accept()

            document = await self.get_document_if_accessible(
                self.user, self.document_id
            )
            if not document:
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "waiting_for_document",
                            "document_id": self.document_id,
                            "message": "Waiting for document creation...",
                            "timestamp": timezone.now().isoformat(),
                        }
                    ),
                )
                logger.info(
                    "User %s connected to upload status for pending document %s",
                    self.user.id,
                    self.document_id,
                )
            else:
                # Send initial status for existing documents
                await self.send_current_status(document)
                logger.info(
                    "User %s connected to upload status for document %s (status: %s)",
                    self.user.id,
                    self.document_id,
                    document.upload_status,
                )

        except Exception as e:
            logger.exception(
                "Error during WebSocket connection for document %s: %s",
                self.document_id,
                str(e),
            )

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        user = getattr(self, "user", None) or self.scope.get("user")
        logger.info(
            "User %s disconnected from upload status for document %s (code: %s)",
            user.id if user else "anonymous",
            getattr(self, "document_id", "unknown"),
            close_code,
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "ping":
                await self.send(
                    text_data=json.dumps(
                        {"type": "pong", "timestamp": str(timezone.now().isoformat())},
                    ),
                )
            elif message_type == "get_status":
                user = self.scope.get("user")
                document = await self.get_document_if_accessible(user, self.document_id)
                if document:
                    await self.send_current_status(document)
            else:
                logger.warning("Unknown message type received: %s", message_type)

        except json.JSONDecodeError:
            logger.error("Invalid JSON received from WebSocket client")
        except Exception:
            logger.exception("Error handling WebSocket message")

    async def upload_status_update(self, event):
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "upload_status",
                        "document_id": event["document_id"],
                        "status": event["status"],
                        "progress": event.get("progress", {}),
                        "error_message": event.get("error_message", ""),
                        "timestamp": event.get("timestamp", ""),
                    },
                ),
            )
        except Exception:
            logger.exception("Error sending upload status update")

    async def upload_progress_update(self, event):
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "upload_progress",
                        "document_id": event["document_id"],
                        "progress": event["progress"],
                        "timestamp": event.get("timestamp", ""),
                    },
                ),
            )
        except Exception:
            logger.exception("Error sending upload progress update")

    async def upload_completed(self, event):
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "upload_completed",
                        "document_id": event["document_id"],
                        "status": "completed",
                        "message": event.get(
                            "message",
                            "Upload completed successfully",
                        ),
                        "timestamp": event.get("timestamp", ""),
                    },
                ),
            )
        except Exception:
            logger.exception("Error sending upload completion update")

    async def upload_failed(self, event):
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "upload_failed",
                        "document_id": event["document_id"],
                        "status": "failed",
                        "error_message": event.get("error_message", "Upload failed"),
                        "timestamp": event.get("timestamp", ""),
                    },
                ),
            )
        except Exception:
            logger.exception("Error sending upload failure update")

    @database_sync_to_async
    def get_document_if_accessible(self, user, document_id):
        try:
            document = Document.objects.get(id=document_id)
            if document.owner_id == user.id:
                return document
            return None
        except ObjectDoesNotExist:
            return None

    async def send_current_status(self, document):
        try:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "current_status",
                        "document_id": document.id,
                        "status": document.upload_status,
                        "progress": document.upload_progress,
                        "error_message": document.upload_error_message,
                        "task_id": document.upload_task_id,
                        "timestamp": timezone.now().isoformat(),
                    },
                ),
            )
        except Exception:
            logger.exception("Error sending current status")
