from .base import *

DEBUG = False

# Tests use the same PostgreSQL server as development (Django creates
# and deletes a separate temporary test database automatically).

# A fast password hasher, used ONLY when running tests.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"