ALTER TABLE job.profession_competencies
    ADD COLUMN IF NOT EXISTS link_type VARCHAR;

UPDATE job.profession_competencies
SET link_type = CASE
    WHEN source = 'esco' AND relation_type = 'essential' THEN 'esco_essential'
    WHEN source = 'esco' AND relation_type = 'optional' THEN 'esco_optional'
    WHEN source IN ('job_parser', 'derived') OR relation_type = 'derived' THEN 'job_derived'
    WHEN source LIKE 'manual%' THEN 'manual'
    ELSE link_type
END
WHERE link_type IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM job.profession_competencies
        WHERE link_type IS NULL
    ) THEN
        RAISE EXCEPTION 'Some profession_competencies rows could not be mapped to link_type.';
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profession_competencies_pkey'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.profession_competencies DROP CONSTRAINT profession_competencies_pkey;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'job'
          AND table_name = 'profession_competencies'
          AND column_name = 'source'
    ) THEN
        ALTER TABLE job.profession_competencies DROP COLUMN source;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'job'
          AND table_name = 'profession_competencies'
          AND column_name = 'relation_type'
    ) THEN
        ALTER TABLE job.profession_competencies DROP COLUMN relation_type;
    END IF;
END
$$;

ALTER TABLE job.profession_competencies
    ALTER COLUMN link_type SET NOT NULL;

ALTER TABLE job.profession_competencies
    ADD CONSTRAINT profession_competencies_pkey PRIMARY KEY (profession_id, competency_id, link_type);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profession_competencies_link_type_check'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.profession_competencies
            ADD CONSTRAINT profession_competencies_link_type_check
            CHECK (link_type IN ('esco_essential', 'esco_optional', 'job_derived', 'manual'));
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profession_competencies_weight_check'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.profession_competencies
            ADD CONSTRAINT profession_competencies_weight_check
            CHECK (
                (link_type IN ('esco_essential', 'esco_optional') AND weight IS NULL) OR
                (link_type IN ('job_derived', 'manual') AND weight IS NOT NULL)
            );
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'competencies_competency_type_check'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.competencies
            ADD CONSTRAINT competencies_competency_type_check
            CHECK (competency_type IS NULL OR competency_type IN ('skill/competence', 'knowledge'));
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profession_labels_label_type_check'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.profession_labels
            ADD CONSTRAINT profession_labels_label_type_check
            CHECK (label_type IN ('preferred', 'alternative', 'hidden'));
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'competency_labels_label_type_check'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.competency_labels
            ADD CONSTRAINT competency_labels_label_type_check
            CHECK (label_type IN ('preferred', 'alternative', 'hidden'));
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'competency_relations_relation_type_check'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.competency_relations
            ADD CONSTRAINT competency_relations_relation_type_check
            CHECK (relation_type IN ('essential', 'optional', 'related'));
    END IF;
END
$$;
