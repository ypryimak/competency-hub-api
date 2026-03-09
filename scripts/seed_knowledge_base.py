"""
Seed the knowledge base directly via SQLAlchemy using the ESCO v1.2.1 EN CSV zip.

The script imports:
  - profession groups (ISCO)
  - professions
  - profession labels
  - competency groups
  - competencies
  - competency labels
  - competency group memberships
  - profession-competency links
  - competency-to-competency relations
  - thematic collections
  - scraped jobs

Usage:
  python scripts/seed_knowledge_base.py
  python scripts/seed_knowledge_base.py --jobs-only
"""

import argparse
import asyncio
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import AsyncSessionLocal
from app.models.models import (
    Competency,
    CompetencyCollection,
    CompetencyCollectionMember,
    CompetencyGroup,
    CompetencyGroupMember,
    CompetencyLabel,
    CompetencyRelation,
    Job,
    Profession,
    ProfessionCollection,
    ProfessionCollectionMember,
    ProfessionCompetency,
    ProfessionGroup,
    ProfessionLabel,
)


if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ESCO_ZIP_PATH = Path(r"C:\Users\ypryi\Downloads\ESCO dataset - v1.2.1 - classification - en - csv.zip")
DATA_DIR = Path(__file__).parent.parent
SCRAPED_JOBS_PATH = DATA_DIR / "scraped_jobs.json"
CHUNK_SIZE = 1000

JOB_PROFESSION_OVERRIDES = {
    "Cloud Architect": "cloud architect",
    "Cybersecurity Analyst": "cybersecurity analyst",
    "Data Analyst": "data analyst",
    "Data Scientist": "data scientist",
    "DevOps Engineer": "cloud DevOps engineer",
    "Front End Developer": "user interface developer",
    "Machine Learning Engineer": "artificial intelligence engineer",
    "Product Manager": "ICT product manager",
    "Quality Assurance Engineer": "quality assurance engineer",
    "Software Engineer": "software engineer",
}

COMPETENCY_COLLECTIONS = {
    "digitalSkillsCollection_en.csv": ("digital", "Digital skills"),
    "digCompSkillsCollection_en.csv": ("digcomp", "DigComp skills"),
    "greenSkillsCollection_en.csv": ("green", "Green skills"),
    "languageSkillsCollection_en.csv": ("language", "Language skills"),
    "researchSkillsCollection_en.csv": ("research", "Research skills"),
    "transversalSkillsCollection_en.csv": ("transversal", "Transversal skills"),
}

PROFESSION_COLLECTIONS = {
    "researchOccupationsCollection_en.csv": ("research", "Research occupations"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed ESCO knowledge base")
    parser.add_argument("--zip-path", type=Path, default=ESCO_ZIP_PATH)
    parser.add_argument("--jobs-only", action="store_true")
    parser.add_argument("--skip-jobs", action="store_true")
    parser.add_argument("--reset-job-data", action="store_true")
    return parser.parse_args()


def read_zip_csv(zip_path: Path, filename: str) -> list[dict[str, str]]:
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(filename) as raw_file:
            text = io.TextIOWrapper(raw_file, encoding="utf-8", newline="")
            return list(csv.DictReader(text))


def load_json(path: Path) -> list | dict:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def chunked(rows: list[dict], size: int = CHUNK_SIZE):
    for index in range(0, len(rows), size):
        yield rows[index : index + size]


def split_labels(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.splitlines() if item.strip()]


async def bulk_insert_ignore(session, table, rows: list[dict], conflict_columns: list[str]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(table).values(rows)
    stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)
    result = await session.execute(stmt)
    return result.rowcount or 0


async def fetch_map(session, model, key_col: str = "name", value_col: str = "id") -> dict[str, int]:
    result = await session.execute(select(getattr(model, value_col), getattr(model, key_col)))
    return {str(row[1]).lower(): row[0] for row in result.all()}


async def fetch_uri_map(session, model) -> dict[str, int]:
    result = await session.execute(select(model.id, model.esco_uri).where(model.esco_uri.isnot(None)))
    return {row[1]: row[0] for row in result.all()}


async def seed_profession_groups(session, zip_path: Path) -> dict[str, int]:
    rows = read_zip_csv(zip_path, "ISCOGroups_en.csv")
    insert_rows = [
        {
            "esco_uri": row["conceptUri"],
            "code": row.get("code") or None,
            "name": row["preferredLabel"],
            "description": row.get("description") or None,
        }
        for row in rows
    ]
    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(session, ProfessionGroup.__table__, chunk, ["esco_uri"])
    await session.commit()

    uri_map = await fetch_uri_map(session, ProfessionGroup)
    relation_rows = read_zip_csv(zip_path, "broaderRelationsOccPillar_en.csv")
    for row in relation_rows:
        if row["conceptType"] != "ISCOGroup" or row["broaderType"] != "ISCOGroup":
            continue
        child_id = uri_map.get(row["conceptUri"])
        parent_id = uri_map.get(row["broaderUri"])
        if child_id and parent_id:
            await session.execute(
                update(ProfessionGroup)
                .where(ProfessionGroup.id == child_id)
                .values(parent_group_id=parent_id)
            )
    await session.commit()
    print(f"  OK Profession groups: {inserted} inserted, {len(uri_map)} total")
    return {row["code"]: uri_map[row["conceptUri"]] for row in rows if row.get("code") and row["conceptUri"] in uri_map}


async def seed_professions(session, zip_path: Path, group_code_map: dict[str, int]) -> dict[str, int]:
    rows = read_zip_csv(zip_path, "occupations_en.csv")
    insert_rows = []
    for row in rows:
        group_id = group_code_map.get(row["iscoGroup"])
        if not group_id:
            continue
        insert_rows.append(
            {
                "esco_uri": row["conceptUri"],
                "code": row.get("code") or None,
                "name": row["preferredLabel"],
                "description": row.get("description") or row.get("definition") or None,
                "profession_group_id": group_id,
            }
        )

    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(session, Profession.__table__, chunk, ["esco_uri"])
    await session.commit()

    uri_map = await fetch_uri_map(session, Profession)
    relation_rows = read_zip_csv(zip_path, "broaderRelationsOccPillar_en.csv")
    for row in relation_rows:
        if row["conceptType"] != "Occupation" or row["broaderType"] != "Occupation":
            continue
        child_id = uri_map.get(row["conceptUri"])
        parent_id = uri_map.get(row["broaderUri"])
        if child_id and parent_id:
            await session.execute(
                update(Profession)
                .where(Profession.id == child_id)
                .values(parent_profession_id=parent_id)
            )
    await session.commit()

    print(f"  OK Professions: {inserted} inserted, {len(uri_map)} total")
    return uri_map


async def seed_profession_labels(session, zip_path: Path, profession_uri_map: dict[str, int]) -> int:
    rows = read_zip_csv(zip_path, "occupations_en.csv")
    insert_rows = []
    for row in rows:
        profession_id = profession_uri_map.get(row["conceptUri"])
        if not profession_id:
            continue
        insert_rows.append(
            {
                "profession_id": profession_id,
                "label": row["preferredLabel"],
                "label_type": "preferred",
                "lang": "en",
            }
        )
        for label in split_labels(row.get("altLabels")):
            insert_rows.append(
                {
                    "profession_id": profession_id,
                    "label": label,
                    "label_type": "alternative",
                    "lang": "en",
                }
            )
        for label in split_labels(row.get("hiddenLabels")):
            insert_rows.append(
                {
                    "profession_id": profession_id,
                    "label": label,
                    "label_type": "hidden",
                    "lang": "en",
                }
            )

    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(
            session,
            ProfessionLabel.__table__,
            chunk,
            ["profession_id", "label", "label_type", "lang"],
        )
    await session.commit()
    print(f"  OK Profession labels: {inserted} inserted")
    return inserted


async def seed_competency_groups(session, zip_path: Path) -> dict[str, int]:
    rows = read_zip_csv(zip_path, "skillGroups_en.csv")
    insert_rows = [
        {
            "esco_uri": row["conceptUri"],
            "code": row.get("code") or None,
            "name": row["preferredLabel"],
            "description": row.get("description") or None,
        }
        for row in rows
    ]
    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(session, CompetencyGroup.__table__, chunk, ["esco_uri"])
    await session.commit()

    uri_map = await fetch_uri_map(session, CompetencyGroup)
    relation_rows = read_zip_csv(zip_path, "broaderRelationsSkillPillar_en.csv")
    for row in relation_rows:
        if row["conceptType"] != "SkillGroup" or row["broaderType"] != "SkillGroup":
            continue
        child_id = uri_map.get(row["conceptUri"])
        parent_id = uri_map.get(row["broaderUri"])
        if child_id and parent_id:
            await session.execute(
                update(CompetencyGroup)
                .where(CompetencyGroup.id == child_id)
                .values(parent_group_id=parent_id)
            )
    await session.commit()
    print(f"  OK Competency groups: {inserted} inserted, {len(uri_map)} total")
    return uri_map


async def seed_competencies(session, zip_path: Path) -> dict[str, int]:
    rows = read_zip_csv(zip_path, "skills_en.csv")
    insert_rows = [
        {
            "esco_uri": row["conceptUri"],
            "name": row["preferredLabel"],
            "description": row.get("description") or row.get("definition") or None,
            "competency_type": row.get("skillType") or None,
        }
        for row in rows
    ]
    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(session, Competency.__table__, chunk, ["esco_uri"])
    await session.commit()
    uri_map = await fetch_uri_map(session, Competency)
    print(f"  OK Competencies: {inserted} inserted, {len(uri_map)} total")
    return uri_map


async def seed_competency_labels(session, zip_path: Path, competency_uri_map: dict[str, int]) -> int:
    rows = read_zip_csv(zip_path, "skills_en.csv")
    insert_rows = []
    for row in rows:
        competency_id = competency_uri_map.get(row["conceptUri"])
        if not competency_id:
            continue
        insert_rows.append(
            {
                "competency_id": competency_id,
                "label": row["preferredLabel"],
                "label_type": "preferred",
                "lang": "en",
            }
        )
        for label in split_labels(row.get("altLabels")):
            insert_rows.append(
                {
                    "competency_id": competency_id,
                    "label": label,
                    "label_type": "alternative",
                    "lang": "en",
                }
            )
        for label in split_labels(row.get("hiddenLabels")):
            insert_rows.append(
                {
                    "competency_id": competency_id,
                    "label": label,
                    "label_type": "hidden",
                    "lang": "en",
                }
            )
    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(
            session,
            CompetencyLabel.__table__,
            chunk,
            ["competency_id", "label", "label_type", "lang"],
        )
    await session.commit()
    print(f"  OK Competency labels: {inserted} inserted")
    return inserted


async def seed_competency_group_members(
    session, zip_path: Path, competency_uri_map: dict[str, int], group_uri_map: dict[str, int]
) -> int:
    rows = read_zip_csv(zip_path, "broaderRelationsSkillPillar_en.csv")
    insert_rows = []
    for row in rows:
        if row["conceptType"] != "KnowledgeSkillCompetence" or row["broaderType"] != "SkillGroup":
            continue
        competency_id = competency_uri_map.get(row["conceptUri"])
        group_id = group_uri_map.get(row["broaderUri"])
        if competency_id and group_id:
            insert_rows.append({"competency_id": competency_id, "group_id": group_id})
    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(
            session,
            CompetencyGroupMember.__table__,
            chunk,
            ["competency_id", "group_id"],
        )
    await session.commit()
    print(f"  OK Competency-group memberships: {inserted} inserted")
    return inserted


async def seed_profession_competencies(
    session, zip_path: Path, profession_uri_map: dict[str, int], competency_uri_map: dict[str, int]
) -> int:
    rows = read_zip_csv(zip_path, "occupationSkillRelations_en.csv")
    relation_weights = {"essential": 1.0, "optional": 0.5}
    insert_rows = []
    for row in rows:
        profession_id = profession_uri_map.get(row["occupationUri"])
        competency_id = competency_uri_map.get(row["skillUri"])
        if profession_id and competency_id:
            insert_rows.append(
                {
                    "profession_id": profession_id,
                    "competency_id": competency_id,
                    "relation_type": row["relationType"],
                    "weight": relation_weights.get(row["relationType"]),
                    "source": "esco",
                }
            )
    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(
            session,
            ProfessionCompetency.__table__,
            chunk,
            ["profession_id", "competency_id", "relation_type"],
        )
    await session.commit()
    print(f"  OK Profession-competency relations: {inserted} inserted")
    return inserted


async def seed_competency_relations(session, zip_path: Path, competency_uri_map: dict[str, int]) -> int:
    rows = read_zip_csv(zip_path, "skillSkillRelations_en.csv")
    insert_rows = []
    for row in rows:
        source_id = competency_uri_map.get(row["originalSkillUri"])
        target_id = competency_uri_map.get(row["relatedSkillUri"])
        if source_id and target_id:
            insert_rows.append(
                {
                    "source_competency_id": source_id,
                    "target_competency_id": target_id,
                    "relation_type": row["relationType"],
                }
            )
    inserted = 0
    for chunk in chunked(insert_rows):
        inserted += await bulk_insert_ignore(
            session,
            CompetencyRelation.__table__,
            chunk,
            ["source_competency_id", "target_competency_id", "relation_type"],
        )
    await session.commit()
    print(f"  OK Competency relations: {inserted} inserted")
    return inserted


async def seed_competency_collections(session, zip_path: Path, competency_uri_map: dict[str, int]) -> None:
    collection_rows = [
        {"code": code, "name": name, "description": None}
        for code, name in COMPETENCY_COLLECTIONS.values()
    ]
    await bulk_insert_ignore(session, CompetencyCollection.__table__, collection_rows, ["code"])
    await session.commit()
    collection_map = await fetch_map(session, CompetencyCollection, key_col="code")

    for filename, (code, _) in COMPETENCY_COLLECTIONS.items():
        rows = read_zip_csv(zip_path, filename)
        insert_rows = []
        for row in rows:
            competency_id = competency_uri_map.get(row["conceptUri"])
            if competency_id:
                insert_rows.append(
                    {"collection_id": collection_map[code], "competency_id": competency_id}
                )
        inserted = 0
        for chunk in chunked(insert_rows):
            inserted += await bulk_insert_ignore(
                session,
                CompetencyCollectionMember.__table__,
                chunk,
                ["collection_id", "competency_id"],
            )
        await session.commit()
        print(f"  OK Collection {code}: {inserted} competency members")


async def seed_profession_collections(session, zip_path: Path, profession_uri_map: dict[str, int]) -> None:
    collection_rows = [
        {"code": code, "name": name, "description": None}
        for code, name in PROFESSION_COLLECTIONS.values()
    ]
    await bulk_insert_ignore(session, ProfessionCollection.__table__, collection_rows, ["code"])
    await session.commit()
    collection_map = await fetch_map(session, ProfessionCollection, key_col="code")

    for filename, (code, _) in PROFESSION_COLLECTIONS.items():
        rows = read_zip_csv(zip_path, filename)
        insert_rows = []
        for row in rows:
            profession_id = profession_uri_map.get(row["conceptUri"])
            if profession_id:
                insert_rows.append(
                    {"collection_id": collection_map[code], "profession_id": profession_id}
                )
        inserted = 0
        for chunk in chunked(insert_rows):
            inserted += await bulk_insert_ignore(
                session,
                ProfessionCollectionMember.__table__,
                chunk,
                ["collection_id", "profession_id"],
            )
        await session.commit()
        print(f"  OK Collection {code}: {inserted} profession members")


def resolve_job_profession(job_position_name: str, profession_name_map: dict[str, int]) -> int | None:
    override = JOB_PROFESSION_OVERRIDES.get(job_position_name)
    if override and override.lower() in profession_name_map:
        return profession_name_map[override.lower()]
    return profession_name_map.get(job_position_name.lower())


async def seed_jobs(session, scraped_jobs: list[dict]) -> int:
    profession_name_map = await fetch_map(session, Profession)
    rows = []
    skipped = set()
    for job in scraped_jobs:
        profession_id = resolve_job_profession(job["position_name"], profession_name_map)
        if not profession_id:
            skipped.add(job["position_name"])
            continue
        rows.append(
            {
                "title": job["title"][:255],
                "description": job["description"],
                "profession_id": profession_id,
            }
        )
    inserted = 0
    for chunk in chunked(rows):
        inserted += await bulk_insert_ignore(
            session,
            Job.__table__,
            chunk,
            ["title", "profession_id"],
        )
    await session.commit()
    if skipped:
        print(f"  WARN Unmatched scraped job professions: {sorted(skipped)}")
    print(f"  OK Jobs: {inserted} inserted")
    return inserted


async def main() -> None:
    args = parse_args()
    if not args.zip_path.exists():
        raise FileNotFoundError(f"ESCO zip not found: {args.zip_path}")

    scraped_jobs = load_json(SCRAPED_JOBS_PATH)

    print("\n=== SEED KNOWLEDGE BASE FROM ESCO ===\n")
    print(f"  zip: {args.zip_path}")
    print(f"  scraped jobs: {len(scraped_jobs)}")

    async with AsyncSessionLocal() as session:
        if args.reset_job_data:
            print("  TRUNCATE job schema tables ...")
            await session.execute(text("TRUNCATE TABLE job.job_competencies CASCADE"))
            await session.execute(text("TRUNCATE TABLE job.jobs CASCADE"))
            await session.commit()

        if not args.jobs_only:
            print("\n--- STEP 1: Profession groups ---")
            group_code_map = await seed_profession_groups(session, args.zip_path)

            print("\n--- STEP 2: Professions ---")
            profession_uri_map = await seed_professions(session, args.zip_path, group_code_map)

            print("\n--- STEP 3: Profession labels ---")
            await seed_profession_labels(session, args.zip_path, profession_uri_map)

            print("\n--- STEP 4: Competency groups ---")
            group_uri_map = await seed_competency_groups(session, args.zip_path)

            print("\n--- STEP 5: Competencies ---")
            competency_uri_map = await seed_competencies(session, args.zip_path)

            print("\n--- STEP 6: Competency labels ---")
            await seed_competency_labels(session, args.zip_path, competency_uri_map)

            print("\n--- STEP 7: Competency group members ---")
            await seed_competency_group_members(session, args.zip_path, competency_uri_map, group_uri_map)

            print("\n--- STEP 8: Profession-competency links ---")
            await seed_profession_competencies(session, args.zip_path, profession_uri_map, competency_uri_map)

            print("\n--- STEP 9: Competency relations ---")
            await seed_competency_relations(session, args.zip_path, competency_uri_map)

            print("\n--- STEP 10: Competency collections ---")
            await seed_competency_collections(session, args.zip_path, competency_uri_map)

            print("\n--- STEP 11: Profession collections ---")
            await seed_profession_collections(session, args.zip_path, profession_uri_map)

        if not args.skip_jobs:
            print("\n--- STEP 12: Jobs ---")
            await seed_jobs(session, scraped_jobs)

    print("\n=== DONE ===\n")


if __name__ == "__main__":
    asyncio.run(main())
