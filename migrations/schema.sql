-- ============================================================
-- Full database schema
-- Run in Supabase SQL Editor
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS job;
CREATE SCHEMA IF NOT EXISTS competency_model;
CREATE SCHEMA IF NOT EXISTS candidate_evaluation;

-- ============================================================
-- PUBLIC
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR NOT NULL,
    email         VARCHAR NOT NULL UNIQUE,
    role          INTEGER,
    password_hash VARCHAR,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    position      VARCHAR,
    company       VARCHAR
);

CREATE TABLE IF NOT EXISTS emails (
    id                  SERIAL PRIMARY KEY,
    email               VARCHAR NOT NULL,
    user_id             INTEGER REFERENCES users(id) ON DELETE SET NULL,
    template_key        VARCHAR NOT NULL,
    status              VARCHAR NOT NULL,
    provider_message_id VARCHAR,
    error_message       TEXT,
    dedupe_key          VARCHAR UNIQUE,
    entity_type         VARCHAR,
    entity_id           INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at             TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token      VARCHAR NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS activity_log (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_type VARCHAR NOT NULL,
    entity_id   INTEGER NOT NULL,
    event_type  VARCHAR NOT NULL,
    old_value   VARCHAR,
    new_value   VARCHAR,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- JOB SCHEMA
-- ============================================================

CREATE TABLE IF NOT EXISTS job.profession_groups (
    id              SERIAL PRIMARY KEY,
    esco_uri        VARCHAR NOT NULL UNIQUE,
    code            VARCHAR,
    name            VARCHAR NOT NULL,
    description     TEXT,
    parent_group_id INTEGER REFERENCES job.profession_groups(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS job.professions (
    id                   SERIAL PRIMARY KEY,
    esco_uri             VARCHAR NOT NULL UNIQUE,
    code                 VARCHAR,
    name                 VARCHAR NOT NULL,
    description          TEXT,
    profession_group_id  INTEGER NOT NULL REFERENCES job.profession_groups(id) ON DELETE RESTRICT,
    parent_profession_id INTEGER REFERENCES job.professions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS job.profession_labels (
    id            SERIAL PRIMARY KEY,
    profession_id INTEGER NOT NULL REFERENCES job.professions(id) ON DELETE CASCADE,
    label         VARCHAR NOT NULL,
    label_type    VARCHAR NOT NULL CHECK (label_type IN ('preferred', 'alternative', 'hidden')),
    lang          VARCHAR NOT NULL,
    UNIQUE (profession_id, label, label_type, lang)
);

CREATE TABLE IF NOT EXISTS job.competency_groups (
    id              SERIAL PRIMARY KEY,
    esco_uri        VARCHAR NOT NULL UNIQUE,
    code            VARCHAR,
    name            VARCHAR NOT NULL,
    description     TEXT,
    parent_group_id INTEGER REFERENCES job.competency_groups(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS job.competencies (
    id              SERIAL PRIMARY KEY,
    esco_uri        VARCHAR UNIQUE,
    name            VARCHAR NOT NULL,
    description     TEXT,
    competency_type VARCHAR CHECK (
        competency_type IS NULL OR competency_type IN ('skill/competence', 'knowledge')
    )
);

CREATE TABLE IF NOT EXISTS job.competency_labels (
    id            SERIAL PRIMARY KEY,
    competency_id INTEGER NOT NULL REFERENCES job.competencies(id) ON DELETE CASCADE,
    label         VARCHAR NOT NULL,
    label_type    VARCHAR NOT NULL CHECK (label_type IN ('preferred', 'alternative', 'hidden')),
    lang          VARCHAR NOT NULL,
    UNIQUE (competency_id, label, label_type, lang)
);

CREATE TABLE IF NOT EXISTS job.competency_group_members (
    competency_id INTEGER NOT NULL REFERENCES job.competencies(id) ON DELETE CASCADE,
    group_id      INTEGER NOT NULL REFERENCES job.competency_groups(id) ON DELETE CASCADE,
    PRIMARY KEY (competency_id, group_id)
);

CREATE TABLE IF NOT EXISTS job.profession_competencies (
    profession_id INTEGER NOT NULL REFERENCES job.professions(id) ON DELETE CASCADE,
    competency_id INTEGER NOT NULL REFERENCES job.competencies(id) ON DELETE CASCADE,
    link_type     VARCHAR NOT NULL CHECK (
        link_type IN ('esco_essential', 'esco_optional', 'job_derived', 'manual')
    ),
    weight        NUMERIC,
    PRIMARY KEY (profession_id, competency_id, link_type),
    CHECK (
        (link_type IN ('esco_essential', 'esco_optional') AND weight IS NULL) OR
        (link_type IN ('job_derived', 'manual') AND weight IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS job.competency_relations (
    source_competency_id INTEGER NOT NULL REFERENCES job.competencies(id) ON DELETE CASCADE,
    target_competency_id INTEGER NOT NULL REFERENCES job.competencies(id) ON DELETE CASCADE,
    relation_type        VARCHAR NOT NULL CHECK (relation_type IN ('essential', 'optional', 'related')),
    PRIMARY KEY (source_competency_id, target_competency_id, relation_type)
);

CREATE TABLE IF NOT EXISTS job.competency_collections (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR NOT NULL UNIQUE,
    name        VARCHAR NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS job.competency_collection_members (
    collection_id INTEGER NOT NULL REFERENCES job.competency_collections(id) ON DELETE CASCADE,
    competency_id INTEGER NOT NULL REFERENCES job.competencies(id) ON DELETE CASCADE,
    PRIMARY KEY (collection_id, competency_id)
);

CREATE TABLE IF NOT EXISTS job.profession_collections (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR NOT NULL UNIQUE,
    name        VARCHAR NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS job.profession_collection_members (
    collection_id INTEGER NOT NULL REFERENCES job.profession_collections(id) ON DELETE CASCADE,
    profession_id INTEGER NOT NULL REFERENCES job.professions(id) ON DELETE CASCADE,
    PRIMARY KEY (collection_id, profession_id)
);

CREATE TABLE IF NOT EXISTS job.jobs (
    id            SERIAL PRIMARY KEY,
    title         VARCHAR NOT NULL,
    description   TEXT NOT NULL,
    profession_id INTEGER NOT NULL REFERENCES job.professions(id) ON DELETE RESTRICT,
    UNIQUE (title, profession_id)
);

CREATE TABLE IF NOT EXISTS job.job_competencies (
    job_id        INTEGER NOT NULL REFERENCES job.jobs(id) ON DELETE CASCADE,
    competency_id INTEGER NOT NULL REFERENCES job.competencies(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, competency_id)
);

-- ============================================================
-- COMPETENCY_MODEL SCHEMA
-- ============================================================

CREATE TABLE IF NOT EXISTS competency_model.models (
    id                    SERIAL PRIMARY KEY,
    user_id               INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    name                  VARCHAR,
    profession_id         INTEGER REFERENCES job.professions(id) ON DELETE SET NULL,
    min_competency_weight NUMERIC,
    max_competency_rank   INTEGER,
    evaluation_deadline   TIMESTAMPTZ,
    status                INTEGER
);

CREATE TABLE IF NOT EXISTS competency_model.experts (
    id       SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES competency_model.models(id) ON DELETE CASCADE,
    user_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    rank     INTEGER NOT NULL,
    weight   NUMERIC
);

CREATE TABLE IF NOT EXISTS competency_model.expert_invites (
    id                  SERIAL PRIMARY KEY,
    model_id            INTEGER NOT NULL REFERENCES competency_model.models(id) ON DELETE CASCADE,
    email               VARCHAR NOT NULL,
    rank                INTEGER NOT NULL,
    token               VARCHAR NOT NULL UNIQUE,
    accepted_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (model_id, email)
);

CREATE TABLE IF NOT EXISTS competency_model.criteria (
    id          SERIAL PRIMARY KEY,
    model_id    INTEGER NOT NULL REFERENCES competency_model.models(id) ON DELETE CASCADE,
    name        VARCHAR NOT NULL,
    description TEXT,
    weight      NUMERIC
);

CREATE TABLE IF NOT EXISTS competency_model.custom_competencies (
    id          SERIAL PRIMARY KEY,
    model_id    INTEGER NOT NULL REFERENCES competency_model.models(id) ON DELETE CASCADE,
    name        VARCHAR NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (model_id, name)
);

CREATE TABLE IF NOT EXISTS competency_model.criterion_ranks (
    criterion_id INTEGER NOT NULL REFERENCES competency_model.criteria(id) ON DELETE CASCADE,
    expert_id    INTEGER NOT NULL REFERENCES competency_model.experts(id) ON DELETE CASCADE,
    rank         INTEGER NOT NULL,
    PRIMARY KEY (criterion_id, expert_id)
);

CREATE TABLE IF NOT EXISTS competency_model.alternatives (
    id                   SERIAL PRIMARY KEY,
    model_id             INTEGER NOT NULL REFERENCES competency_model.models(id) ON DELETE CASCADE,
    competency_id        INTEGER REFERENCES job.competencies(id) ON DELETE RESTRICT,
    custom_competency_id INTEGER REFERENCES competency_model.custom_competencies(id) ON DELETE CASCADE,
    weight               NUMERIC,
    final_weight         NUMERIC,
    UNIQUE (model_id, competency_id),
    UNIQUE (model_id, custom_competency_id),
    CHECK (
        (competency_id IS NOT NULL AND custom_competency_id IS NULL) OR
        (competency_id IS NULL AND custom_competency_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS competency_model.alternative_ranks (
    alternative_id INTEGER NOT NULL REFERENCES competency_model.alternatives(id) ON DELETE CASCADE,
    expert_id      INTEGER NOT NULL REFERENCES competency_model.experts(id) ON DELETE CASCADE,
    criterion_id   INTEGER NOT NULL REFERENCES competency_model.criteria(id) ON DELETE CASCADE,
    rank           INTEGER NOT NULL,
    PRIMARY KEY (alternative_id, expert_id, criterion_id)
);

-- ============================================================
-- CANDIDATE_EVALUATION SCHEMA
-- ============================================================

CREATE TABLE IF NOT EXISTS candidate_evaluation.selections (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_id            INTEGER REFERENCES competency_model.models(id) ON DELETE SET NULL,
    evaluation_deadline TIMESTAMPTZ,
    status              INTEGER
);

CREATE TABLE IF NOT EXISTS candidate_evaluation.candidates (
    id                   SERIAL PRIMARY KEY,
    user_id              INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name                 VARCHAR,
    email                VARCHAR,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    profession_id        INTEGER NOT NULL REFERENCES job.professions(id) ON DELETE RESTRICT,
    cv_file_path         VARCHAR,
    cv_original_filename VARCHAR,
    cv_mime_type         VARCHAR,
    cv_uploaded_at       TIMESTAMPTZ,
    cv_parse_status      VARCHAR NOT NULL DEFAULT 'not_uploaded',
    cv_parsed_at         TIMESTAMPTZ,
    cv_parse_error       TEXT
);

CREATE TABLE IF NOT EXISTS candidate_evaluation.candidate_selections (
    candidate_id INTEGER NOT NULL REFERENCES candidate_evaluation.candidates(id) ON DELETE CASCADE,
    selection_id INTEGER NOT NULL REFERENCES candidate_evaluation.selections(id) ON DELETE CASCADE,
    score        NUMERIC,
    rank         INTEGER,
    PRIMARY KEY (candidate_id, selection_id)
);

CREATE TABLE IF NOT EXISTS candidate_evaluation.candidate_competencies (
    candidate_id  INTEGER NOT NULL REFERENCES candidate_evaluation.candidates(id) ON DELETE CASCADE,
    competency_id INTEGER NOT NULL REFERENCES job.competencies(id) ON DELETE CASCADE,
    PRIMARY KEY (candidate_id, competency_id)
);

CREATE TABLE IF NOT EXISTS candidate_evaluation.experts (
    id           SERIAL PRIMARY KEY,
    selection_id INTEGER NOT NULL REFERENCES candidate_evaluation.selections(id) ON DELETE CASCADE,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    weight       NUMERIC
);

CREATE TABLE IF NOT EXISTS candidate_evaluation.selection_criteria (
    id                   SERIAL PRIMARY KEY,
    selection_id         INTEGER NOT NULL REFERENCES candidate_evaluation.selections(id) ON DELETE CASCADE,
    alternative_id       INTEGER REFERENCES competency_model.alternatives(id) ON DELETE SET NULL,
    competency_id        INTEGER REFERENCES job.competencies(id) ON DELETE SET NULL,
    custom_competency_id INTEGER REFERENCES competency_model.custom_competencies(id) ON DELETE SET NULL,
    name                 VARCHAR NOT NULL,
    weight               NUMERIC,
    UNIQUE (selection_id, alternative_id),
    CHECK (
        (competency_id IS NOT NULL AND custom_competency_id IS NULL) OR
        (competency_id IS NULL AND custom_competency_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS candidate_evaluation.expert_invites (
    id                  SERIAL PRIMARY KEY,
    selection_id        INTEGER NOT NULL REFERENCES candidate_evaluation.selections(id) ON DELETE CASCADE,
    email               VARCHAR NOT NULL,
    weight              NUMERIC,
    token               VARCHAR NOT NULL UNIQUE,
    accepted_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (selection_id, email)
);

CREATE TABLE IF NOT EXISTS candidate_evaluation.candidate_scores (
    candidate_id           INTEGER NOT NULL REFERENCES candidate_evaluation.candidates(id) ON DELETE CASCADE,
    expert_id              INTEGER NOT NULL REFERENCES candidate_evaluation.experts(id) ON DELETE CASCADE,
    selection_criterion_id INTEGER NOT NULL REFERENCES candidate_evaluation.selection_criteria(id) ON DELETE CASCADE,
    score                  INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    PRIMARY KEY (candidate_id, expert_id, selection_criterion_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_profession_groups_parent
    ON job.profession_groups(parent_group_id);
CREATE INDEX IF NOT EXISTS idx_professions_group
    ON job.professions(profession_group_id);
CREATE INDEX IF NOT EXISTS idx_professions_parent
    ON job.professions(parent_profession_id);
CREATE INDEX IF NOT EXISTS idx_professions_name_trgm
    ON job.professions USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_competency_groups_parent
    ON job.competency_groups(parent_group_id);
CREATE INDEX IF NOT EXISTS idx_competencies_name_trgm
    ON job.competencies USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_prof_comp_profession
    ON job.profession_competencies(profession_id);
CREATE INDEX IF NOT EXISTS idx_prof_comp_competency
    ON job.profession_competencies(competency_id);
CREATE INDEX IF NOT EXISTS idx_jobs_profession
    ON job.jobs(profession_id);
CREATE INDEX IF NOT EXISTS idx_job_comp_job
    ON job.job_competencies(job_id);

CREATE INDEX IF NOT EXISTS idx_models_user
    ON competency_model.models(user_id);
CREATE INDEX IF NOT EXISTS idx_models_profession
    ON competency_model.models(profession_id);
CREATE INDEX IF NOT EXISTS idx_models_status
    ON competency_model.models(status);
CREATE INDEX IF NOT EXISTS idx_experts_model
    ON competency_model.experts(model_id);
CREATE INDEX IF NOT EXISTS idx_expert_invites_model
    ON competency_model.expert_invites(model_id);
CREATE INDEX IF NOT EXISTS idx_expert_invites_email
    ON competency_model.expert_invites(email);
CREATE INDEX IF NOT EXISTS idx_criteria_model
    ON competency_model.criteria(model_id);
CREATE INDEX IF NOT EXISTS idx_custom_competencies_model
    ON competency_model.custom_competencies(model_id);
CREATE INDEX IF NOT EXISTS idx_alternatives_model
    ON competency_model.alternatives(model_id);

CREATE INDEX IF NOT EXISTS idx_selections_user
    ON candidate_evaluation.selections(user_id);
CREATE INDEX IF NOT EXISTS idx_selections_model
    ON candidate_evaluation.selections(model_id);
CREATE INDEX IF NOT EXISTS idx_candidates_profession
    ON candidate_evaluation.candidates(profession_id);
CREATE INDEX IF NOT EXISTS idx_candidates_user
    ON candidate_evaluation.candidates(user_id);
CREATE INDEX IF NOT EXISTS idx_sel_experts_sel
    ON candidate_evaluation.experts(selection_id);
CREATE INDEX IF NOT EXISTS idx_selection_criteria_selection
    ON candidate_evaluation.selection_criteria(selection_id);
CREATE INDEX IF NOT EXISTS idx_selection_invites_selection
    ON candidate_evaluation.expert_invites(selection_id);
CREATE INDEX IF NOT EXISTS idx_selection_invites_email
    ON candidate_evaluation.expert_invites(email);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user
    ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_user_created
    ON activity_log(user_id, created_at DESC);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.profession_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.professions ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.profession_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.competency_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.competencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.competency_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.competency_group_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.profession_competencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.competency_relations ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.competency_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.competency_collection_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.profession_collections ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.profession_collection_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job.job_competencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE competency_model.models ENABLE ROW LEVEL SECURITY;
ALTER TABLE competency_model.experts ENABLE ROW LEVEL SECURITY;
ALTER TABLE competency_model.expert_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE competency_model.criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE competency_model.custom_competencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE competency_model.criterion_ranks ENABLE ROW LEVEL SECURITY;
ALTER TABLE competency_model.alternatives ENABLE ROW LEVEL SECURITY;
ALTER TABLE competency_model.alternative_ranks ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_evaluation.selections ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_evaluation.candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_evaluation.candidate_selections ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_evaluation.candidate_competencies ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_evaluation.experts ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_evaluation.selection_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_evaluation.expert_invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_evaluation.candidate_scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON users FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON emails FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON password_reset_tokens FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all" ON activity_log FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "authenticated_read" ON job.profession_groups FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.profession_groups FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.professions FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.professions FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.profession_labels FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.profession_labels FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.competency_groups FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.competency_groups FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.competencies FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.competencies FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.competency_labels FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.competency_labels FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.competency_group_members FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.competency_group_members FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.profession_competencies FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.profession_competencies FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.competency_relations FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.competency_relations FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.competency_collections FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.competency_collections FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.competency_collection_members FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.competency_collection_members FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.profession_collections FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.profession_collections FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.profession_collection_members FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.profession_collection_members FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.jobs FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.jobs FOR ALL TO service_role USING (true);
CREATE POLICY "authenticated_read" ON job.job_competencies FOR SELECT TO authenticated USING (true);
CREATE POLICY "service_role_write" ON job.job_competencies FOR ALL TO service_role USING (true);

CREATE POLICY "service_role_all" ON competency_model.models FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON competency_model.experts FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON competency_model.expert_invites FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON competency_model.criteria FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON competency_model.custom_competencies FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON competency_model.criterion_ranks FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON competency_model.alternatives FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON competency_model.alternative_ranks FOR ALL TO service_role USING (true);

CREATE POLICY "service_role_all" ON candidate_evaluation.selections FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON candidate_evaluation.candidates FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON candidate_evaluation.candidate_selections FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON candidate_evaluation.candidate_competencies FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON candidate_evaluation.experts FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON candidate_evaluation.selection_criteria FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON candidate_evaluation.expert_invites FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_all" ON candidate_evaluation.candidate_scores FOR ALL TO service_role USING (true);
