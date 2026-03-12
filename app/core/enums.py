from enum import Enum, IntEnum


class UserRole(IntEnum):
    ADMIN = 1
    USER = 2


class UserRoleName(str, Enum):
    HR = "hr"
    ADMIN = "admin"


class ModelStatus(IntEnum):
    DRAFT = 1
    EXPERT_EVALUATION = 2
    COMPLETED = 3
    CANCELLED = 4


class SelectionStatus(IntEnum):
    DRAFT = 1
    EXPERT_EVALUATION = 2
    COMPLETED = 3
    CANCELLED = 4


class WorkflowStatusName(str, Enum):
    DRAFT = "draft"
    EXPERT_EVALUATION = "expert_evaluation"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CandidateCVParseStatus(str, Enum):
    NOT_UPLOADED = "not_uploaded"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PARSED = "parsed"
    FAILED = "failed"


class SkillType(IntEnum):
    SPECIALIZED = 1
    CERTIFICATION = 2
    COMMON = 3


class LetterType(IntEnum):
    WELCOME = 1
    EXPERT_INVITE = 2
    EXPERT_REMINDER = 3
    DEADLINE_REMINDER = 4
    DEADLINE_REACHED = 5
    ALL_EVALUATIONS_COLLECTED = 6
    MODEL_RESULT = 7
    SELECTION_RESULT = 8


class EmailDeliveryStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class EmailTemplateKey(str, Enum):
    WELCOME = "welcome"
    EXPERT_INVITE = "expert_invite"
    EXPERT_DEADLINE_REMINDER = "expert_deadline_reminder"
    OWNER_DEADLINE_REMINDER = "owner_deadline_reminder"
    OWNER_DEADLINE_REACHED_COMPLETED = "owner_deadline_reached_completed"
    OWNER_DEADLINE_REACHED_CANCELLED = "owner_deadline_reached_cancelled"
    OWNER_INVITE_ACCEPTED = "owner_invite_accepted"
    OWNER_SUBMISSION_RECEIVED = "owner_submission_received"


def get_user_role_name(role_code: int | None) -> UserRoleName | None:
    if role_code == UserRole.ADMIN:
        return UserRoleName.ADMIN
    if role_code == UserRole.USER:
        return UserRoleName.HR
    return None


def get_workflow_status_name(status_code: int | None) -> WorkflowStatusName | None:
    if status_code in (ModelStatus.DRAFT, SelectionStatus.DRAFT):
        return WorkflowStatusName.DRAFT
    if status_code in (ModelStatus.EXPERT_EVALUATION, SelectionStatus.EXPERT_EVALUATION):
        return WorkflowStatusName.EXPERT_EVALUATION
    if status_code in (ModelStatus.COMPLETED, SelectionStatus.COMPLETED):
        return WorkflowStatusName.COMPLETED
    if status_code in (ModelStatus.CANCELLED, SelectionStatus.CANCELLED):
        return WorkflowStatusName.CANCELLED
    return None
