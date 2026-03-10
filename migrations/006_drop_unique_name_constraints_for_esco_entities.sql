DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'profession_groups_name_key'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.profession_groups
            DROP CONSTRAINT profession_groups_name_key;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'professions_name_key'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.professions
            DROP CONSTRAINT professions_name_key;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'competency_groups_name_key'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.competency_groups
            DROP CONSTRAINT competency_groups_name_key;
    END IF;
END
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'competencies_name_key'
          AND connamespace = 'job'::regnamespace
    ) THEN
        ALTER TABLE job.competencies
            DROP CONSTRAINT competencies_name_key;
    END IF;
END
$$;
