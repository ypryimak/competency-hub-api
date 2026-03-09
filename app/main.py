from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1.router import api_router

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
    # startup
    yield
    # shutdown


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

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
async def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
