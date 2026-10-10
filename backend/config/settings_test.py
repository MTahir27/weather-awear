"""Settings for the test suite: deterministic and independent of any local .env."""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-secret-key")

from config.settings import *  # noqa: F403

TOMTOM_API_KEY = "test-tomtom-key"
