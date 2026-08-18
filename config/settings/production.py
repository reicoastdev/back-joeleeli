from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env


def required_env(name):
    value = env(name, default="")
    if not value:
        raise ImproperlyConfigured(f"The {name} environment variable is required.")
    return value


DEBUG = False
SECRET_KEY = required_env("DJANGO_SECRET_KEY")
required_env("DATABASE_URL")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "The DJANGO_ALLOWED_HOSTS environment variable is required."
    )

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
