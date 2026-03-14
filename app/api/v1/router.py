from fastapi import APIRouter
from app.api.v1.endpoints import auth, knowledge_base, competency_models, candidate_selection, activity

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(knowledge_base.router)
api_router.include_router(competency_models.router)
api_router.include_router(candidate_selection.router)
api_router.include_router(activity.router)
# Фаза 5: mailing, reporting — додамо далі
