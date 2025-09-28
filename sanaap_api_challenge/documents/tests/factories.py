import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from factory import fuzzy

from sanaap_api_challenge.documents.models import Access
from sanaap_api_challenge.documents.models import Document
from sanaap_api_challenge.documents.models import Share

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False
    is_superuser = False


class SuperuserFactory(UserFactory):
    is_staff = True
    is_superuser = True
    username = factory.Sequence(lambda n: f"admin{n}")


class DocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Document

    title = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("text", max_nb_chars=200)
    file_name = factory.Faker("file_name")
    file_path = factory.Faker("file_path", depth=3)
    file_size = fuzzy.FuzzyInteger(1024, 10 * 1024 * 1024)  # 1KB to 10MB
    content_type = "application/pdf"
    file_hash = factory.Faker("sha256")
    owner = factory.SubFactory(UserFactory)
    created_by = factory.SelfAttribute("owner")
    updated_by = factory.SelfAttribute("owner")
    status = "active"
    is_public = False
    download_count = 0


class PublicDocumentFactory(DocumentFactory):
    is_public = True


class ShareFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Share

    document = factory.SubFactory(DocumentFactory)
    shared_with = factory.SubFactory(UserFactory)
    shared_by = factory.SelfAttribute("document.owner")
    permission_level = "view"
    expires_at = None
    access_count = 0


class ExpiredShareFactory(ShareFactory):
    expires_at = factory.LazyFunction(
        lambda: timezone.now() - timezone.timedelta(days=1),
    )


class AccessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Access

    document = factory.SubFactory(DocumentFactory)
    user = factory.SubFactory(UserFactory)
    action = "view"
    ip_address = factory.Faker("ipv4")
    user_agent = factory.Faker("user_agent")
    additional_info = factory.Dict({})
    success = True
    error_message = ""
