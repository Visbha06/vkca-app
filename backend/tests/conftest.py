"""Shared pytest environment configuration."""

import os

# Settings are loaded while route and integration test modules are imported.
# Keep the production secret mandatory while giving tests an isolated signing key.
os.environ.setdefault("JWT_SECRET", "pytest-only-jwt-secret-never-use-in-production")
