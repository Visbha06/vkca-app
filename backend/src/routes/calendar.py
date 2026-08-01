"""Calendar API route group.

The foundational phase registers the stable route prefix. Read and mutation
handlers are added by their user-story phases once the shared service exists.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/calendar", tags=["calendar"])
