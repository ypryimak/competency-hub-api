"""
Candidate Selection Router

/selections/*          - HR-user (selection owner)
/expert/selections/*   - Expert entry point
"""
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.models import User
from app.schemas.candidate_selection import (
    AddCandidateToSelection,
    CVParseResponse,
    CandidateCreate,
    CandidateCVSignedUrl,
    CandidateOut,
    CandidateSelectionOut,
    CandidateWithCompetencies,
    ExpertSelectionDetail,
    ExpertScoringStatus,
    ExpertScoringSubmit,
    SelectionCreate,
    SelectionDetail,
    SelectionExpertCreate,
    SelectionExpertInviteCreate,
    SelectionExpertInviteOut,
    SelectionExpertInviteUpdate,
    SelectionExpertUpdate,
    SelectionExpertOut,
    SelectionOut,
    SelectionUpdate,
    VIKORResult,
)
from app.services.candidate_selection_service import candidate_selection_service

router = APIRouter()


@router.get("/selections", response_model=list[SelectionOut], tags=["Candidate Selection"])
async def list_selections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.list_selections(db, current_user.id)


@router.post("/selections", response_model=SelectionOut, status_code=201, tags=["Candidate Selection"])
async def create_selection(
    data: SelectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.create_selection(db, data, current_user.id)


@router.get("/selections/{selection_id}", response_model=SelectionDetail, tags=["Candidate Selection"])
async def get_selection(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.get_selection(db, selection_id, current_user.id)


@router.patch("/selections/{selection_id}", response_model=SelectionOut, tags=["Candidate Selection"])
async def update_selection(
    selection_id: int,
    data: SelectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.update_selection(
        db, selection_id, current_user.id, data
    )


@router.delete("/selections/{selection_id}", status_code=204, tags=["Candidate Selection"])
async def delete_selection(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await candidate_selection_service.delete_selection(db, selection_id, current_user.id)


@router.post("/selections/{selection_id}/submit", response_model=SelectionOut, tags=["Candidate Selection"])
async def submit_selection(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.submit_selection(
        db, selection_id, current_user.id
    )


@router.post("/selections/{selection_id}/cancel", response_model=SelectionOut, tags=["Candidate Selection"])
async def cancel_selection(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.cancel_selection(
        db, selection_id, current_user.id
    )


@router.post("/selections/{selection_id}/calculate", response_model=VIKORResult, tags=["Candidate Selection"])
async def calculate_vikor(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.calculate_vikor(
        db, selection_id, current_user.id
    )


@router.get("/selections/{selection_id}/results", response_model=VIKORResult, tags=["Candidate Selection"])
async def get_results(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.get_selection_results(
        db, selection_id, current_user.id
    )


@router.get("/candidates", response_model=list[CandidateOut], tags=["Candidate Selection"])
async def list_candidates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.list_candidates(db, current_user.id)


@router.post("/candidates", response_model=CandidateOut, status_code=201, tags=["Candidate Selection"])
async def create_candidate(
    data: CandidateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.create_candidate(db, data, current_user.id)


@router.get("/candidates/{candidate_id}", response_model=CandidateWithCompetencies, tags=["Candidate Selection"])
async def get_candidate(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.get_candidate(db, candidate_id, current_user.id)


@router.post("/candidates/{candidate_id}/cv", response_model=CandidateOut, tags=["Candidate Selection"])
async def upload_candidate_cv(
    candidate_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = await file.read()
    return await candidate_selection_service.upload_candidate_cv(
        db,
        candidate_id,
        current_user.id,
        file.filename,
        file.content_type,
        content,
    )


@router.delete("/candidates/{candidate_id}/cv", response_model=CandidateOut, tags=["Candidate Selection"])
async def delete_candidate_cv(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.delete_candidate_cv(db, candidate_id, current_user.id)


@router.get("/candidates/{candidate_id}/cv-url", response_model=CandidateCVSignedUrl, tags=["Candidate Selection"])
async def get_candidate_cv_url(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.get_candidate_cv_url(db, candidate_id, current_user.id)


@router.post("/candidates/{candidate_id}/parse-cv", response_model=CVParseResponse, tags=["Candidate Selection"])
async def parse_candidate_cv(
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.parse_candidate_cv(db, candidate_id, current_user.id)


@router.post(
    "/selections/{selection_id}/candidates",
    response_model=CandidateSelectionOut,
    status_code=201,
    tags=["Candidate Selection"],
)
async def add_candidate_to_selection(
    selection_id: int,
    data: AddCandidateToSelection,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.add_candidate_to_selection(
        db, selection_id, current_user.id, data.candidate_id
    )


@router.delete(
    "/selections/{selection_id}/candidates/{candidate_id}",
    status_code=204,
    tags=["Candidate Selection"],
)
async def remove_candidate_from_selection(
    selection_id: int,
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await candidate_selection_service.remove_candidate_from_selection(
        db, selection_id, current_user.id, candidate_id
    )


@router.post(
    "/selections/{selection_id}/experts",
    response_model=SelectionExpertOut,
    status_code=201,
    tags=["Candidate Selection"],
)
async def add_expert(
    selection_id: int,
    data: SelectionExpertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.add_expert(
        db, selection_id, current_user.id, data
    )


@router.delete(
    "/selections/{selection_id}/experts/{expert_id}",
    status_code=204,
    tags=["Candidate Selection"],
)
async def remove_expert(
    selection_id: int,
    expert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await candidate_selection_service.remove_expert(
        db, selection_id, current_user.id, expert_id
    )


@router.patch(
    "/selections/{selection_id}/experts/{expert_id}",
    response_model=SelectionExpertOut,
    tags=["Candidate Selection"],
)
async def update_expert(
    selection_id: int,
    expert_id: int,
    data: SelectionExpertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.update_expert(
        db, selection_id, expert_id, current_user.id, data
    )


@router.get(
    "/selections/{selection_id}/expert-invites",
    response_model=list[SelectionExpertInviteOut],
    tags=["Candidate Selection"],
)
async def list_expert_invites(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.list_expert_invites(db, selection_id, current_user.id)


@router.post(
    "/selections/{selection_id}/expert-invites",
    response_model=SelectionExpertInviteOut,
    status_code=201,
    tags=["Candidate Selection"],
)
async def create_expert_invite(
    selection_id: int,
    data: SelectionExpertInviteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.create_expert_invite(
        db, selection_id, current_user.id, data
    )


@router.patch(
    "/selections/{selection_id}/expert-invites/{invite_id}",
    response_model=SelectionExpertInviteOut,
    tags=["Candidate Selection"],
)
async def update_expert_invite(
    selection_id: int,
    invite_id: int,
    data: SelectionExpertInviteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.update_expert_invite(
        db, selection_id, invite_id, current_user.id, data
    )


@router.delete(
    "/selections/{selection_id}/expert-invites/{invite_id}",
    status_code=204,
    tags=["Candidate Selection"],
)
async def delete_expert_invite(
    selection_id: int,
    invite_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await candidate_selection_service.delete_expert_invite(
        db, selection_id, invite_id, current_user.id
    )


@router.get("/expert/selections", response_model=list[SelectionOut], tags=["Expert"])
async def expert_list_selections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.list_selections_as_expert(db, current_user.id)


@router.get("/expert/selections/{selection_id}", response_model=ExpertSelectionDetail, tags=["Expert"])
async def expert_get_selection(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.get_selection_as_expert(
        db, selection_id, current_user.id
    )


@router.get("/expert/selection-invites", response_model=list[SelectionExpertInviteOut], tags=["Expert"])
async def expert_list_selection_invites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.list_pending_invites_for_user(db, current_user.id)


@router.post("/expert/selection-invites/{token}/accept", response_model=SelectionExpertOut, tags=["Expert"])
async def expert_accept_selection_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.accept_expert_invite(db, token, current_user.id)


@router.get(
    "/expert/selections/{selection_id}/scoring-status",
    response_model=ExpertScoringStatus,
    tags=["Expert"],
)
async def expert_scoring_status(
    selection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.get_expert_scoring_status(
        db, selection_id, current_user.id
    )


@router.post(
    "/expert/selections/{selection_id}/score",
    response_model=ExpertScoringStatus,
    tags=["Expert"],
)
async def expert_submit_scores(
    selection_id: int,
    data: ExpertScoringSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await candidate_selection_service.submit_expert_scores(
        db, selection_id, current_user.id, data
    )
