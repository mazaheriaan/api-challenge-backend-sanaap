from django.urls import path

from .consumers import UploadStatusConsumer

websocket_urlpatterns = [
    path("ws/upload/<int:document_id>/", UploadStatusConsumer.as_asgi()),
]
