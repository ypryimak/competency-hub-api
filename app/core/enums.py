from enum import Enum, IntEnum


class UserRole(IntEnum):
    ADMIN = 1
    USER = 2  # HR-спеціаліст, може також бути експертом


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


class SkillType(IntEnum):
    SPECIALIZED = 1   # Specialized Skill
    CERTIFICATION = 2 # Certification
    COMMON = 3        # Common Skill


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
