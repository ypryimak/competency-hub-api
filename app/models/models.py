"""
SQLAlchemy models for the application database.

The knowledge-base part is now ESCO-oriented and uses professions,
competencies, groups, labels, collections, and profession-to-competency links.
"""
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Integer,
    String,
    Text,
    Numeric,
    Boolean,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    role: Mapped[Optional[int]] = mapped_column(Integer)
    password_hash: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    emails: Mapped[List["Email"]] = relationship(back_populates="user")
    competency_models: Mapped[List["CompetencyModel"]] = relationship(back_populates="creator")
    accepted_competency_model_invites: Mapped[List["ExpertInvite"]] = relationship(
        foreign_keys="ExpertInvite.accepted_by_user_id",
        back_populates="accepted_by_user",
    )
    selections: Mapped[List["Selection"]] = relationship(back_populates="creator")
    candidates: Mapped[List["Candidate"]] = relationship(back_populates="creator")
    accepted_selection_invites: Mapped[List["SelectionExpertInvite"]] = relationship(
        foreign_keys="SelectionExpertInvite.accepted_by_user_id",
        back_populates="accepted_by_user",
    )


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("public.users.id"))
    template_key: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    dedupe_key: Mapped[Optional[str]] = mapped_column(String, unique=True)
    entity_type: Mapped[Optional[str]] = mapped_column(String)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="emails")


class ProfessionGroup(Base):
    __tablename__ = "profession_groups"
    __table_args__ = {"schema": "job"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    esco_uri: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    code: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    parent_group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job.profession_groups.id")
    )

    parent_group: Mapped[Optional["ProfessionGroup"]] = relationship(
        remote_side=[id],
        back_populates="child_groups",
    )
    child_groups: Mapped[List["ProfessionGroup"]] = relationship(back_populates="parent_group")
    professions: Mapped[List["Profession"]] = relationship(back_populates="profession_group")


class Profession(Base):
    __tablename__ = "professions"
    __table_args__ = {"schema": "job"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    esco_uri: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    code: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    profession_group_id: Mapped[int] = mapped_column(
        ForeignKey("job.profession_groups.id"),
        nullable=False,
    )
    parent_profession_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job.professions.id")
    )

    profession_group: Mapped["ProfessionGroup"] = relationship(back_populates="professions")
    parent_profession: Mapped[Optional["Profession"]] = relationship(
        remote_side=[id],
        back_populates="child_professions",
    )
    child_professions: Mapped[List["Profession"]] = relationship(back_populates="parent_profession")
    labels: Mapped[List["ProfessionLabel"]] = relationship(
        back_populates="profession",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[List["Job"]] = relationship(
        back_populates="profession",
        cascade="all, delete-orphan",
    )
    profession_competencies: Mapped[List["ProfessionCompetency"]] = relationship(
        back_populates="profession",
        cascade="all, delete-orphan",
    )
    collection_memberships: Mapped[List["ProfessionCollectionMember"]] = relationship(
        back_populates="profession",
        cascade="all, delete-orphan",
    )
    competency_models: Mapped[List["CompetencyModel"]] = relationship(back_populates="profession")
    candidates: Mapped[List["Candidate"]] = relationship(back_populates="profession")


class ProfessionLabel(Base):
    __tablename__ = "profession_labels"
    __table_args__ = (
        UniqueConstraint("profession_id", "label", "label_type", "lang"),
        {"schema": "job"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profession_id: Mapped[int] = mapped_column(
        ForeignKey("job.professions.id"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    label_type: Mapped[str] = mapped_column(String, nullable=False)
    lang: Mapped[str] = mapped_column(String, nullable=False, default="en")

    profession: Mapped["Profession"] = relationship(back_populates="labels")


class CompetencyGroup(Base):
    __tablename__ = "competency_groups"
    __table_args__ = {"schema": "job"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    esco_uri: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    code: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    parent_group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job.competency_groups.id")
    )

    parent_group: Mapped[Optional["CompetencyGroup"]] = relationship(
        remote_side=[id],
        back_populates="child_groups",
    )
    child_groups: Mapped[List["CompetencyGroup"]] = relationship(back_populates="parent_group")
    group_members: Mapped[List["CompetencyGroupMember"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class Competency(Base):
    __tablename__ = "competencies"
    __table_args__ = {"schema": "job"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    esco_uri: Mapped[Optional[str]] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    competency_type: Mapped[Optional[str]] = mapped_column(String)

    labels: Mapped[List["CompetencyLabel"]] = relationship(
        back_populates="competency",
        cascade="all, delete-orphan",
    )
    group_memberships: Mapped[List["CompetencyGroupMember"]] = relationship(
        back_populates="competency",
        cascade="all, delete-orphan",
    )
    profession_links: Mapped[List["ProfessionCompetency"]] = relationship(
        back_populates="competency",
        cascade="all, delete-orphan",
    )
    job_competencies: Mapped[List["JobCompetency"]] = relationship(
        back_populates="competency"
    )
    alternatives: Mapped[List["Alternative"]] = relationship(back_populates="competency")
    candidate_competencies: Mapped[List["CandidateCompetency"]] = relationship(
        back_populates="competency"
    )
    source_relations: Mapped[List["CompetencyRelation"]] = relationship(
        foreign_keys="CompetencyRelation.source_competency_id",
        back_populates="source_competency",
        cascade="all, delete-orphan",
    )
    target_relations: Mapped[List["CompetencyRelation"]] = relationship(
        foreign_keys="CompetencyRelation.target_competency_id",
        back_populates="target_competency",
        cascade="all, delete-orphan",
    )
    collection_memberships: Mapped[List["CompetencyCollectionMember"]] = relationship(
        back_populates="competency",
        cascade="all, delete-orphan",
    )


class CompetencyLabel(Base):
    __tablename__ = "competency_labels"
    __table_args__ = (
        UniqueConstraint("competency_id", "label", "label_type", "lang"),
        {"schema": "job"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("job.competencies.id"),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    label_type: Mapped[str] = mapped_column(String, nullable=False)
    lang: Mapped[str] = mapped_column(String, nullable=False, default="en")

    competency: Mapped["Competency"] = relationship(back_populates="labels")


class CompetencyGroupMember(Base):
    __tablename__ = "competency_group_members"
    __table_args__ = (
        UniqueConstraint("competency_id", "group_id"),
        {"schema": "job"},
    )

    competency_id: Mapped[int] = mapped_column(
        ForeignKey("job.competencies.id"),
        primary_key=True,
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("job.competency_groups.id"),
        primary_key=True,
    )

    competency: Mapped["Competency"] = relationship(back_populates="group_memberships")
    group: Mapped["CompetencyGroup"] = relationship(back_populates="group_members")


class ProfessionCompetency(Base):
    __tablename__ = "profession_competencies"
    __table_args__ = (
        UniqueConstraint("profession_id", "competency_id", "link_type"),
        {"schema": "job"},
    )

    profession_id: Mapped[int] = mapped_column(
        ForeignKey("job.professions.id"),
        primary_key=True,
    )
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("job.competencies.id"),
        primary_key=True,
    )
    link_type: Mapped[str] = mapped_column(String, primary_key=True)
    weight: Mapped[Optional[float]] = mapped_column(Numeric)

    profession: Mapped["Profession"] = relationship(back_populates="profession_competencies")
    competency: Mapped["Competency"] = relationship(back_populates="profession_links")


class CompetencyRelation(Base):
    __tablename__ = "competency_relations"
    __table_args__ = (
        UniqueConstraint("source_competency_id", "target_competency_id", "relation_type"),
        {"schema": "job"},
    )

    source_competency_id: Mapped[int] = mapped_column(
        ForeignKey("job.competencies.id"),
        primary_key=True,
    )
    target_competency_id: Mapped[int] = mapped_column(
        ForeignKey("job.competencies.id"),
        primary_key=True,
    )
    relation_type: Mapped[str] = mapped_column(String, primary_key=True)

    source_competency: Mapped["Competency"] = relationship(
        foreign_keys=[source_competency_id],
        back_populates="source_relations",
    )
    target_competency: Mapped["Competency"] = relationship(
        foreign_keys=[target_competency_id],
        back_populates="target_relations",
    )


class CompetencyCollection(Base):
    __tablename__ = "competency_collections"
    __table_args__ = {"schema": "job"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    members: Mapped[List["CompetencyCollectionMember"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
    )


class CompetencyCollectionMember(Base):
    __tablename__ = "competency_collection_members"
    __table_args__ = (
        UniqueConstraint("collection_id", "competency_id"),
        {"schema": "job"},
    )

    collection_id: Mapped[int] = mapped_column(
        ForeignKey("job.competency_collections.id"),
        primary_key=True,
    )
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("job.competencies.id"),
        primary_key=True,
    )

    collection: Mapped["CompetencyCollection"] = relationship(back_populates="members")
    competency: Mapped["Competency"] = relationship(back_populates="collection_memberships")


class ProfessionCollection(Base):
    __tablename__ = "profession_collections"
    __table_args__ = {"schema": "job"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    members: Mapped[List["ProfessionCollectionMember"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
    )


class ProfessionCollectionMember(Base):
    __tablename__ = "profession_collection_members"
    __table_args__ = (
        UniqueConstraint("collection_id", "profession_id"),
        {"schema": "job"},
    )

    collection_id: Mapped[int] = mapped_column(
        ForeignKey("job.profession_collections.id"),
        primary_key=True,
    )
    profession_id: Mapped[int] = mapped_column(
        ForeignKey("job.professions.id"),
        primary_key=True,
    )

    collection: Mapped["ProfessionCollection"] = relationship(back_populates="members")
    profession: Mapped["Profession"] = relationship(back_populates="collection_memberships")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("title", "profession_id"),
        {"schema": "job"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    profession_id: Mapped[int] = mapped_column(
        ForeignKey("job.professions.id"),
        nullable=False,
    )

    profession: Mapped["Profession"] = relationship(back_populates="jobs")
    job_competencies: Mapped[List["JobCompetency"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class JobCompetency(Base):
    __tablename__ = "job_competencies"
    __table_args__ = (
        UniqueConstraint("job_id", "competency_id"),
        {"schema": "job"},
    )

    job_id: Mapped[int] = mapped_column(ForeignKey("job.jobs.id"), primary_key=True)
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("job.competencies.id"),
        primary_key=True,
    )

    job: Mapped["Job"] = relationship(back_populates="job_competencies")
    competency: Mapped["Competency"] = relationship(back_populates="job_competencies")


class CompetencyModel(Base):
    __tablename__ = "models"
    __table_args__ = {"schema": "competency_model"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("public.users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    name: Mapped[Optional[str]] = mapped_column(String)
    profession_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job.professions.id"))
    min_competency_weight: Mapped[Optional[float]] = mapped_column(Numeric)
    max_competency_rank: Mapped[Optional[int]] = mapped_column(Integer)
    evaluation_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[Optional[int]] = mapped_column(Integer)

    creator: Mapped["User"] = relationship(back_populates="competency_models")
    profession: Mapped[Optional["Profession"]] = relationship(back_populates="competency_models")
    experts: Mapped[List["ModelExpert"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )
    expert_invites: Mapped[List["ExpertInvite"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )
    criteria: Mapped[List["Criterion"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )
    custom_competencies: Mapped[List["CustomCompetency"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )
    alternatives: Mapped[List["Alternative"]] = relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )


class ModelExpert(Base):
    __tablename__ = "experts"
    __table_args__ = {"schema": "competency_model"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.models.id"),
        nullable=False,
    )
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("public.users.id"))
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Numeric)

    model: Mapped["CompetencyModel"] = relationship(back_populates="experts")
    user: Mapped[Optional["User"]] = relationship()
    criterion_ranks: Mapped[List["CriterionRank"]] = relationship(back_populates="expert")
    alternative_ranks: Mapped[List["AlternativeRank"]] = relationship(back_populates="expert")


class ExpertInvite(Base):
    __tablename__ = "expert_invites"
    __table_args__ = (
        UniqueConstraint("model_id", "email"),
        {"schema": "competency_model"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.models.id"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    accepted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("public.users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    model: Mapped["CompetencyModel"] = relationship(back_populates="expert_invites")
    accepted_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[accepted_by_user_id],
        back_populates="accepted_competency_model_invites",
    )


class Criterion(Base):
    __tablename__ = "criteria"
    __table_args__ = {"schema": "competency_model"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.models.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Numeric)

    model: Mapped["CompetencyModel"] = relationship(back_populates="criteria")
    criterion_ranks: Mapped[List["CriterionRank"]] = relationship(back_populates="criterion")
    alternative_ranks: Mapped[List["AlternativeRank"]] = relationship(back_populates="criterion")


class CustomCompetency(Base):
    __tablename__ = "custom_competencies"
    __table_args__ = (
        UniqueConstraint("model_id", "name"),
        {"schema": "competency_model"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.models.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    model: Mapped["CompetencyModel"] = relationship(back_populates="custom_competencies")
    alternatives: Mapped[List["Alternative"]] = relationship(
        back_populates="custom_competency",
        cascade="all, delete-orphan",
    )


class CriterionRank(Base):
    __tablename__ = "criterion_ranks"
    __table_args__ = (
        UniqueConstraint("criterion_id", "expert_id"),
        {"schema": "competency_model"},
    )

    criterion_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.criteria.id"),
        primary_key=True,
    )
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.experts.id"),
        primary_key=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    criterion: Mapped["Criterion"] = relationship(back_populates="criterion_ranks")
    expert: Mapped["ModelExpert"] = relationship(back_populates="criterion_ranks")


class Alternative(Base):
    __tablename__ = "alternatives"
    __table_args__ = (
        UniqueConstraint("model_id", "competency_id"),
        UniqueConstraint("model_id", "custom_competency_id"),
        {"schema": "competency_model"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.models.id"),
        nullable=False,
    )
    competency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("job.competencies.id"),
        nullable=True,
    )
    custom_competency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("competency_model.custom_competencies.id"),
        nullable=True,
    )
    weight: Mapped[Optional[float]] = mapped_column(Numeric)
    final_weight: Mapped[Optional[float]] = mapped_column(Numeric)

    model: Mapped["CompetencyModel"] = relationship(back_populates="alternatives")
    competency: Mapped["Competency"] = relationship(back_populates="alternatives")
    custom_competency: Mapped[Optional["CustomCompetency"]] = relationship(
        back_populates="alternatives"
    )
    alternative_ranks: Mapped[List["AlternativeRank"]] = relationship(
        back_populates="alternative"
    )


class AlternativeRank(Base):
    __tablename__ = "alternative_ranks"
    __table_args__ = (
        UniqueConstraint("alternative_id", "expert_id", "criterion_id"),
        {"schema": "competency_model"},
    )

    alternative_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.alternatives.id"),
        primary_key=True,
    )
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.experts.id"),
        primary_key=True,
    )
    criterion_id: Mapped[int] = mapped_column(
        ForeignKey("competency_model.criteria.id"),
        primary_key=True,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)

    alternative: Mapped["Alternative"] = relationship(back_populates="alternative_ranks")
    expert: Mapped["ModelExpert"] = relationship(back_populates="alternative_ranks")
    criterion: Mapped["Criterion"] = relationship(back_populates="alternative_ranks")


class Selection(Base):
    __tablename__ = "selections"
    __table_args__ = {"schema": "candidate_evaluation"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("public.users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    model_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("competency_model.models.id")
    )
    evaluation_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[Optional[int]] = mapped_column(Integer)

    creator: Mapped["User"] = relationship(back_populates="selections")
    competency_model: Mapped[Optional["CompetencyModel"]] = relationship()
    candidates: Mapped[List["CandidateSelection"]] = relationship(
        back_populates="selection",
        cascade="all, delete-orphan",
    )
    experts: Mapped[List["SelectionExpert"]] = relationship(
        back_populates="selection",
        cascade="all, delete-orphan",
    )
    criteria: Mapped[List["SelectionCriterion"]] = relationship(
        back_populates="selection",
        cascade="all, delete-orphan",
    )
    expert_invites: Mapped[List["SelectionExpertInvite"]] = relationship(
        back_populates="selection",
        cascade="all, delete-orphan",
    )


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = {"schema": "candidate_evaluation"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("public.users.id"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String)
    email: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    profession_id: Mapped[int] = mapped_column(
        ForeignKey("job.professions.id"),
        nullable=False,
    )
    cv_file_path: Mapped[Optional[str]] = mapped_column(String)
    cv_original_filename: Mapped[Optional[str]] = mapped_column(String)
    cv_mime_type: Mapped[Optional[str]] = mapped_column(String)
    cv_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cv_parse_status: Mapped[Optional[str]] = mapped_column(String)
    cv_parsed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cv_parse_error: Mapped[Optional[str]] = mapped_column(Text)

    creator: Mapped["User"] = relationship(back_populates="candidates")
    profession: Mapped["Profession"] = relationship(back_populates="candidates")
    candidate_selections: Mapped[List["CandidateSelection"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
    competencies: Mapped[List["CandidateCompetency"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class CandidateSelection(Base):
    __tablename__ = "candidate_selections"
    __table_args__ = (
        UniqueConstraint("candidate_id", "selection_id"),
        {"schema": "candidate_evaluation"},
    )

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.candidates.id"),
        primary_key=True,
    )
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.selections.id"),
        primary_key=True,
    )
    score: Mapped[Optional[float]] = mapped_column(Numeric)
    rank: Mapped[Optional[int]] = mapped_column(Integer)

    candidate: Mapped["Candidate"] = relationship(back_populates="candidate_selections")
    selection: Mapped["Selection"] = relationship(back_populates="candidates")


class CandidateCompetency(Base):
    __tablename__ = "candidate_competencies"
    __table_args__ = (
        UniqueConstraint("candidate_id", "competency_id"),
        {"schema": "candidate_evaluation"},
    )

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.candidates.id"),
        primary_key=True,
    )
    competency_id: Mapped[int] = mapped_column(
        ForeignKey("job.competencies.id"),
        primary_key=True,
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="competencies")
    competency: Mapped["Competency"] = relationship(back_populates="candidate_competencies")


class SelectionExpert(Base):
    __tablename__ = "experts"
    __table_args__ = {"schema": "candidate_evaluation"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.selections.id"),
        nullable=False,
    )
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("public.users.id"))
    weight: Mapped[Optional[float]] = mapped_column(Numeric)

    selection: Mapped["Selection"] = relationship(back_populates="experts")
    user: Mapped[Optional["User"]] = relationship()
    scores: Mapped[List["CandidateScore"]] = relationship(back_populates="expert")


class SelectionCriterion(Base):
    __tablename__ = "selection_criteria"
    __table_args__ = (
        UniqueConstraint("selection_id", "alternative_id"),
        {"schema": "candidate_evaluation"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.selections.id"),
        nullable=False,
    )
    alternative_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("competency_model.alternatives.id")
    )
    competency_id: Mapped[Optional[int]] = mapped_column(ForeignKey("job.competencies.id"))
    custom_competency_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("competency_model.custom_competencies.id")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Numeric)

    selection: Mapped["Selection"] = relationship(back_populates="criteria")
    alternative: Mapped[Optional["Alternative"]] = relationship()
    competency: Mapped[Optional["Competency"]] = relationship()
    custom_competency: Mapped[Optional["CustomCompetency"]] = relationship()
    scores: Mapped[List["CandidateScore"]] = relationship(back_populates="selection_criterion")


class SelectionExpertInvite(Base):
    __tablename__ = "expert_invites"
    __table_args__ = (
        UniqueConstraint("selection_id", "email"),
        {"schema": "candidate_evaluation"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    selection_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.selections.id"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    weight: Mapped[Optional[float]] = mapped_column(Numeric)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    accepted_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("public.users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    selection: Mapped["Selection"] = relationship(back_populates="expert_invites")
    accepted_by_user: Mapped[Optional["User"]] = relationship(
        foreign_keys=[accepted_by_user_id],
        back_populates="accepted_selection_invites",
    )


class CandidateScore(Base):
    __tablename__ = "candidate_scores"
    __table_args__ = (
        UniqueConstraint("candidate_id", "expert_id", "selection_criterion_id"),
        {"schema": "candidate_evaluation"},
    )

    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.candidates.id"),
        primary_key=True,
    )
    expert_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.experts.id"),
        primary_key=True,
    )
    selection_criterion_id: Mapped[int] = mapped_column(
        ForeignKey("candidate_evaluation.selection_criteria.id"),
        primary_key=True,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)

    candidate: Mapped["Candidate"] = relationship()
    expert: Mapped["SelectionExpert"] = relationship(back_populates="scores")
    selection_criterion: Mapped["SelectionCriterion"] = relationship(back_populates="scores")
