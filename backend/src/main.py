"""FastAPI application entry point."""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import get_settings
from src.middleware.error_handlers import register_error_handlers
from src.middleware.request_body_limit import RequestBodyLimitMiddleware
from src.routes.auth import router as auth_router
from src.routes.business_audit import router as business_audit_router
from src.routes.calendar import router as calendar_router
from src.routes.coaches import router as coaches_router
from src.routes.dashboard import router as dashboard_router
from src.routes.data_quality import router as data_quality_router
from src.routes.match_scoring import match_scoring_router
from src.routes.matches import router as matches_router
from src.routes.performances import router as performances_router
from src.routes.players import router as players_router
from src.routes.rag import router as rag_router
from src.routes.stats import router as stats_router
from src.routes.teams import router as teams_router
from src.routes.users import router as users_router
from src.services.rate_limiter import rate_limiter

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(business_audit_router)
api_router.include_router(calendar_router)
api_router.include_router(coaches_router)
api_router.include_router(data_quality_router)
api_router.include_router(dashboard_router)
api_router.include_router(matches_router)
api_router.include_router(match_scoring_router)
api_router.include_router(performances_router)
api_router.include_router(players_router)
api_router.include_router(rag_router)
api_router.include_router(stats_router)
api_router.include_router(teams_router)
api_router.include_router(users_router)


@api_router.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report whether the API process is available."""

    return {"status": "ok"}


app = FastAPI(title="VKCA Cricket Team Management API")
app.state.rate_limiter = rate_limiter
register_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_bytes=get_settings().request_body_max_bytes,
)
app.include_router(api_router)
