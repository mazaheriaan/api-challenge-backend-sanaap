from django.conf import settings
from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from .views import DocumentViewSet
from .views import MyDocumentsView
from .views import PublicDocumentsView
from .views import ShareViewSet

app_name = "documents"

router = DefaultRouter() if settings.DEBUG else SimpleRouter()
router.register(r"items", DocumentViewSet, basename="document")
router.register(r"shares", ShareViewSet, basename="share")

urlpatterns = [
    path("my/", MyDocumentsView.as_view(), name="my-documents"),
    path("public/", PublicDocumentsView.as_view(), name="public-documents"),
    path("", include(router.urls)),
]
