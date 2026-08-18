from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="django-insecure-local-development-key-only",
)
ALLOWED_HOSTS = env.list(
    "DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"]
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
