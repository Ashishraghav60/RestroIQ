
from django.core.exceptions import ImproperlyConfigured
from .base import *

DEBUG = False

if SECRET_KEY == "unsafe-development-key-change-before-deployment":
    raise ImproperlyConfigured(
        "Set a secure DJANGO_SECRET_KEY in production."
    )

if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must be configured in production."
    )

SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True

CSRF_COOKIE_SECURE = True

SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "DENY"

SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
