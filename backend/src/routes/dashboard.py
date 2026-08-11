"""Dashboard route boundary.

The authenticated dashboard endpoint is implemented in a later phase. Keeping
the module boundary in place now lets contract tooling and feature imports
stabilize without exposing an incomplete route.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

