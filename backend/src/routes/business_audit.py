"""Route boundary for the Head Coach business activity audit APIs."""

from fastapi import APIRouter

router = APIRouter(prefix="/audit-log", tags=["business-audit"])

