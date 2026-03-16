"""
Competency model router.

Two entry points:
  /competency-models/... for HR users who own the model
  /expert/... for experts who provide evaluations
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import User
from app.schemas.common import ExpertWorkspaceSummaryOut
from app.schemas.competency_model import (
    AlternativeCreate,
    AlternativeOut,
    AlternativeRecommendation,
    CompetencyModelCreate,
    CompetencyModelDetail,
    CompetencyModelOut,
    CompetencyModelUpdate,
    ExpertCompetencyModelDetail,
    CriterionCreate,
    CriterionOut,
    CriterionUpdate,
    CustomCompetencyCreate,
    CustomCompetencyOut,
    CustomCompetencyUpdate,
    ExpertEvaluationStatus,
    ExpertEvaluationSubmit,
    ExpertInviteCreate,
    ExpertInviteOut,
    ExpertInviteUpdate,
    ExpertReorderRequest,
    ModelExpertCreate,
    ModelExpertOut,
    ModelExpertUpdate,
    ModelSubmitRequest,
    OPAResult,
)
from app.services.candidate_selection_service import candidate_selection_service
from app.services.competency_model_service import competency_model_service

router = APIRouter()


@router.get(
    "/competency-models",
    response_model=list[CompetencyModelOut],
    tags=["Competency Models"],
)
async def list_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List competency models owned by the current user."""
    return await competency_model_service.list_models(db, current_user.id)


@router.post(
    "/competency-models",
    response_model=CompetencyModelOut,
    status_code=201,
    tags=["Competency Models"],
)
async def create_model(
    data: CompetencyModelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a competency model."""
    return await competency_model_service.create_model(db, data, current_user.id)


@router.get(
    "/competency-models/{model_id}",
    response_model=CompetencyModelDetail,
    tags=["Competency Models"],
)
async def get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.get_model(db, model_id, current_user.id)


@router.patch(
    "/competency-models/{model_id}",
    response_model=CompetencyModelOut,
    tags=["Competency Models"],
)
async def update_model(
    model_id: int,
    data: CompetencyModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the model name and/or profession while it is in draft."""
    return await competency_model_service.update_model(db, model_id, current_user.id, data)


@router.delete("/competency-models/{model_id}", status_code=204, tags=["Competency Models"])
async def delete_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a competency model while it is in draft."""
    await competency_model_service.delete_model(db, model_id, current_user.id)


@router.post(
    "/competency-models/{model_id}/submit",
    response_model=CompetencyModelOut,
    tags=["Competency Models"],
)
async def submit_model(
    model_id: int,
    data: ModelSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a draft model to expert evaluation and send expert invites."""
    return await competency_model_service.submit_model(db, model_id, current_user.id, data)


@router.post(
    "/competency-models/{model_id}/cancel",
    response_model=CompetencyModelOut,
    tags=["Competency Models"],
)
async def cancel_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel a competency model."""
    return await competency_model_service.cancel_model(db, model_id, current_user.id)


@router.post(
    "/competency-models/{model_id}/calculate",
    response_model=OPAResult,
    tags=["Competency Models"],
)
async def calculate_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run OPA manually to finalize the evaluation outcome."""
    return await competency_model_service.calculate_opa(db, model_id, current_user.id)


@router.post(
    "/competency-models/{model_id}/experts",
    response_model=ModelExpertOut,
    status_code=201,
    tags=["Competency Models"],
)
async def add_expert(
    model_id: int,
    data: ModelExpertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.add_expert(db, model_id, current_user.id, data)


@router.patch(
    "/competency-models/{model_id}/experts/{expert_id}",
    response_model=ModelExpertOut,
    tags=["Competency Models"],
)
async def update_expert(
    model_id: int,
    expert_id: int,
    data: ModelExpertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.update_expert(
        db, model_id, expert_id, current_user.id, data
    )


@router.post(
    "/competency-models/{model_id}/experts/reorder",
    status_code=204,
    tags=["Competency Models"],
)
async def reorder_experts(
    model_id: int,
    data: ExpertReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await competency_model_service.reorder_experts(db, model_id, current_user.id, data)


@router.delete(
    "/competency-models/{model_id}/experts/{expert_id}",
    status_code=204,
    tags=["Competency Models"],
)
async def remove_expert(
    model_id: int,
    expert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await competency_model_service.remove_expert(db, model_id, expert_id, current_user.id)


@router.get(
    "/competency-models/{model_id}/expert-invites",
    response_model=list[ExpertInviteOut],
    tags=["Competency Models"],
)
async def list_expert_invites(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.list_expert_invites(db, model_id, current_user.id)


@router.post(
    "/competency-models/{model_id}/expert-invites",
    response_model=ExpertInviteOut,
    status_code=201,
    tags=["Competency Models"],
)
async def create_expert_invite(
    model_id: int,
    data: ExpertInviteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.create_expert_invite(
        db, model_id, current_user.id, data
    )


@router.patch(
    "/competency-models/{model_id}/expert-invites/{invite_id}",
    response_model=ExpertInviteOut,
    tags=["Competency Models"],
)
async def update_expert_invite(
    model_id: int,
    invite_id: int,
    data: ExpertInviteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.update_expert_invite(
        db, model_id, invite_id, current_user.id, data
    )


@router.delete(
    "/competency-models/{model_id}/expert-invites/{invite_id}",
    status_code=204,
    tags=["Competency Models"],
)
async def delete_expert_invite(
    model_id: int,
    invite_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await competency_model_service.delete_expert_invite(
        db, model_id, invite_id, current_user.id
    )


@router.post(
    "/competency-models/{model_id}/criteria",
    response_model=CriterionOut,
    status_code=201,
    tags=["Competency Models"],
)
async def add_criterion(
    model_id: int,
    data: CriterionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.add_criterion(db, model_id, current_user.id, data)


@router.patch(
    "/competency-models/{model_id}/criteria/{criterion_id}",
    response_model=CriterionOut,
    tags=["Competency Models"],
)
async def update_criterion(
    model_id: int,
    criterion_id: int,
    data: CriterionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.update_criterion(
        db, model_id, criterion_id, current_user.id, data
    )


@router.delete(
    "/competency-models/{model_id}/criteria/{criterion_id}",
    status_code=204,
    tags=["Competency Models"],
)
async def remove_criterion(
    model_id: int,
    criterion_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await competency_model_service.remove_criterion(
        db, model_id, criterion_id, current_user.id
    )


@router.get(
    "/competency-models/{model_id}/custom-competencies",
    response_model=list[CustomCompetencyOut],
    tags=["Competency Models"],
)
async def list_custom_competencies(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.list_custom_competencies(
        db, model_id, current_user.id
    )


@router.post(
    "/competency-models/{model_id}/custom-competencies",
    response_model=CustomCompetencyOut,
    status_code=201,
    tags=["Competency Models"],
)
async def create_custom_competency(
    model_id: int,
    data: CustomCompetencyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.create_custom_competency(
        db, model_id, current_user.id, data
    )


@router.patch(
    "/competency-models/{model_id}/custom-competencies/{custom_competency_id}",
    response_model=CustomCompetencyOut,
    tags=["Competency Models"],
)
async def update_custom_competency(
    model_id: int,
    custom_competency_id: int,
    data: CustomCompetencyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.update_custom_competency(
        db, model_id, custom_competency_id, current_user.id, data
    )


@router.delete(
    "/competency-models/{model_id}/custom-competencies/{custom_competency_id}",
    status_code=204,
    tags=["Competency Models"],
)
async def delete_custom_competency(
    model_id: int,
    custom_competency_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await competency_model_service.delete_custom_competency(
        db, model_id, custom_competency_id, current_user.id
    )


@router.get(
    "/competency-models/{model_id}/recommendations",
    response_model=list[AlternativeRecommendation],
    tags=["Competency Models"],
)
async def get_recommendations(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recommended competencies for the model profession."""
    return await competency_model_service.get_recommendations(db, model_id, current_user.id)


@router.post(
    "/competency-models/{model_id}/alternatives",
    response_model=AlternativeOut,
    status_code=201,
    tags=["Competency Models"],
)
async def add_alternative(
    model_id: int,
    data: AlternativeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.add_alternative(db, model_id, current_user.id, data)


@router.delete(
    "/competency-models/{model_id}/alternatives/{alternative_id}",
    status_code=204,
    tags=["Competency Models"],
)
async def remove_alternative(
    model_id: int,
    alternative_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await competency_model_service.remove_alternative(
        db, model_id, alternative_id, current_user.id
    )


@router.get(
    "/expert/workspace-summary",
    response_model=ExpertWorkspaceSummaryOut,
    tags=["Expert"],
)
async def expert_workspace_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model_invites = await competency_model_service.get_pending_invite_count_for_user(
        db, current_user.id
    )
    selection_invites = await candidate_selection_service.get_pending_invite_count_for_user(
        db, current_user.id
    )
    open_model_evaluations, completed_model_evaluations = (
        await competency_model_service.get_expert_assignment_counts(db, current_user.id)
    )
    open_candidate_scorings, completed_candidate_scorings = (
        await candidate_selection_service.get_expert_assignment_counts(db, current_user.id)
    )

    pending_invites = model_invites + selection_invites
    completed_tasks = completed_model_evaluations + completed_candidate_scorings
    total_notifications = (
        pending_invites + open_model_evaluations + open_candidate_scorings
    )

    return ExpertWorkspaceSummaryOut(
        has_workspace_access=(pending_invites + completed_tasks + open_model_evaluations + open_candidate_scorings)
        > 0,
        pending_invites=pending_invites,
        open_model_evaluations=open_model_evaluations,
        open_candidate_scorings=open_candidate_scorings,
        completed_tasks=completed_tasks,
        total_notifications=total_notifications,
    )


@router.get(
    "/expert/competency-models",
    response_model=list[CompetencyModelOut],
    tags=["Expert"],
)
async def expert_list_models(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List models where the current user is an active expert."""
    return await competency_model_service.list_models_as_expert(db, current_user.id)


@router.get(
    "/expert/competency-models/{model_id}",
    response_model=ExpertCompetencyModelDetail,
    tags=["Expert"],
)
async def expert_get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.get_model_as_expert(db, model_id, current_user.id)


@router.get(
    "/expert/competency-model-invites",
    response_model=list[ExpertInviteOut],
    tags=["Expert"],
)
async def expert_list_invites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.list_pending_invites_for_user(db, current_user.id)


@router.post(
    "/expert/competency-model-invites/{token}/accept",
    response_model=ModelExpertOut,
    tags=["Expert"],
)
async def expert_accept_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await competency_model_service.accept_expert_invite(db, token, current_user.id)


@router.get(
    "/expert/competency-models/{model_id}/evaluation-status",
    response_model=ExpertEvaluationStatus,
    tags=["Expert"],
)
async def expert_evaluation_status(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current evaluation progress for the expert."""
    return await competency_model_service.get_expert_evaluation_status(
        db, model_id, current_user.id
    )


@router.post(
    "/expert/competency-models/{model_id}/evaluate",
    response_model=ExpertEvaluationStatus,
    tags=["Expert"],
)
async def expert_submit_evaluation(
    model_id: int,
    data: ExpertEvaluationSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit or overwrite expert rankings for criteria and alternatives."""
    return await competency_model_service.submit_expert_evaluation(
        db, model_id, current_user.id, data
    )
