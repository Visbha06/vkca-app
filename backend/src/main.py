"""FastAPI application entry point."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.middleware.error_handlers import register_error_handlers

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report whether the API process is available."""

    return {"status": "ok"}


app = FastAPI(title="VKCA Cricket Team Management API")
register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
