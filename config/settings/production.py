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
configured_hosts = env.list("DJANGO_ALLOWED_HOSTS", default=[])
railway_hosts = [
    env("RAILWAY_PUBLIC_DOMAIN", default="").strip(),
    env("RAILWAY_PRIVATE_DOMAIN", default="").strip(),
]
deployment_hosts = [host for host in [*configured_hosts, *railway_hosts] if host]
if not deployment_hosts:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS or a Railway domain environment variable is required."
    )
ALLOWED_HOSTS = list(dict.fromkeys([*deployment_hosts, "healthcheck.railway.app"]))
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
}
