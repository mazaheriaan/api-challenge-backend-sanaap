from .base import *  # noqa: F403
from .base import INSTALLED_APPS
from .base import MIDDLEWARE
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="tjNYcxFmP0jtBhbjaRNC8NjcqkxiOh9fNcIPIPDuIZ9uoUtI1WToa4NPEMBUF9m6",
)
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
ALLOWED_HOSTS = ["localhost", "0.0.0.0", "127.0.0.1"]  # noqa: S104

# CACHES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "",
    },
}

# django-debug-toolbar
# ------------------------------------------------------------------------------
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#prerequisites
INSTALLED_APPS += ["debug_toolbar"]
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#middleware
MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]
# https://django-debug-toolbar.readthedocs.io/en/latest/configuration.html#debug-toolbar-config
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": [
        "debug_toolbar.panels.redirects.RedirectsPanel",
        # Disable profiling panel due to an issue with Python 3.12+:
        # https://github.com/jazzband/django-debug-toolbar/issues/1875
        "debug_toolbar.panels.profiling.ProfilingPanel",
    ],
    "SHOW_TEMPLATE_CONTEXT": True,
}
# https://django-debug-toolbar.readthedocs.io/en/latest/installation.html#internal-ips
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
if env("USE_DOCKER") == "yes":
    import socket

    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join([*ip.split(".")[:-1], "1"]) for ip in ips]

# django-extensions
# ------------------------------------------------------------------------------
# https://django-extensions.readthedocs.io/en/latest/installation_instructions.html#configuration
INSTALLED_APPS += ["django_extensions"]
# Celery
# ------------------------------------------------------------------------------

# https://docs.celeryq.dev/en/stable/userguide/configuration.html#task-eager-propagates
CELERY_TASK_EAGER_PROPAGATES = True

# Document Upload Settings - Development
# ------------------------------------------------------------------------------
# SECURITY: Strict limits to prevent DoS attacks even in development
# Files larger than this will be rejected by Django before reaching our app
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB in memory max
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 1024  # 1GB total request size max

# Allow more fields for development (increased to handle extreme multipart uploads)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000

FILE_UPLOAD_HANDLERS = [
    "sanaap_api_challenge.documents.utils.upload_handlers.SecureFileUploadHandler",
    "sanaap_api_challenge.documents.utils.upload_handlers.MemoryEfficientUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]

# Application-level file size limits (enforced in serializers)
MAX_FILE_SIZES = {
    "document": 200 * 1024 * 1024,  # 200MB
    "image": 50 * 1024 * 1024,  # 50MB
    "audio": 300 * 1024 * 1024,  # 300MB
    "video": 500 * 1024 * 1024,  # 500MB (reduced from 1GB for safety)
    "archive": 300 * 1024 * 1024,  # 300MB
    "code": 50 * 1024 * 1024,  # 50MB
    "default": 200 * 1024 * 1024,  # 200MB (reduced from 500MB)
}
