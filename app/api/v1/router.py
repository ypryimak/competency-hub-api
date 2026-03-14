from fastapi import APIRouter

from app.api.v1.endpoints import (
    activity,
    auth,
    candidate_selection,
    competency_models,
    knowledge_base,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(knowledge_base.router)
api_router.include_router(competency_models.router)
api_router.include_router(candidate_selection.router)
api_router.include_router(activity.router)
