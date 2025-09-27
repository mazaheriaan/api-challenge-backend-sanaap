from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet
from .views import MyDocumentsView
from .views import PublicDocumentsView
from .views import ShareViewSet

app_name = "documents"

router = DefaultRouter()
router.register(r"documents", DocumentViewSet, basename="document")
router.register(r"shares", ShareViewSet, basename="share")

urlpatterns = [
    path("", include(router.urls)),
    path("my/", MyDocumentsView.as_view(), name="my-documents"),
    path("public/", PublicDocumentsView.as_view(), name="public-documents"),
]
