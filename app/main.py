import logging
import logging.config
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter
from app.api.v1.router import api_router
from app.api.v1.openapi_metadata import apply_openapi_metadata
from app.services.background_jobs import background_job_runner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

APP_DESCRIPTION = """
Backend for competency models, expert evaluation, and candidate selection.

This service uses the ESCO classification of the European Commission.
"""

OPENAPI_TAGS = [
    {"name": "Auth", "description": "Authentication and current user operations."},
    {"name": "Knowledge Base: Profession Groups", "description": "Profession group taxonomy."},
    {"name": "Knowledge Base: Professions", "description": "Professions, profession labels, and profession-competency links."},
    {"name": "Knowledge Base: Profession Collections", "description": "Thematic profession collections and their members."},
    {"name": "Knowledge Base: Competency Groups", "description": "Competency group taxonomy."},
    {"name": "Knowledge Base: Competencies", "description": "Competencies, labels, and group memberships."},
    {"name": "Knowledge Base: Competency Relations", "description": "Graph-like links between competencies."},
    {"name": "Knowledge Base: Competency Collections", "description": "Thematic competency collections and their members."},
    {"name": "Knowledge Base: Jobs", "description": "Vacancies and vacancy-competency extraction."},
    {"name": "Competency Models", "description": "OPA-based competency model building."},
    {"name": "Expert", "description": "Expert-facing evaluation and invite acceptance endpoints."},
    {"name": "Candidate Selection", "description": "Candidate evaluation and VIKOR-based ranking."},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    background_job_runner.start()
    yield
    await background_job_runner.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=APP_DESCRIPTION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
apply_openapi_metadata(app)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
async def health():
    return {"status": "ok"}
