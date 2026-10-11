
import os

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


load_dotenv()


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Check your .env file."
        )

    return database_url


def setup_application_tables() -> None:
    with psycopg.connect(get_database_url()) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS candidate_profiles (
                candidate_id BIGSERIAL PRIMARY KEY,
                profile_key TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                profile_data JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS job_search_runs (
                run_id BIGSERIAL PRIMARY KEY,
                thread_id TEXT UNIQUE NOT NULL,
                candidate_id BIGINT NOT NULL
                    REFERENCES candidate_profiles(candidate_id),
                keyword TEXT NOT NULL,
                location TEXT NOT NULL,
                decision TEXT NOT NULL DEFAULT 'pending',
                ranked_jobs JSONB NOT NULL DEFAULT '[]'::jsonb,
                selected_job JSONB,
                application_materials JSONB,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

    print("Application history tables are ready.")


def to_dict(value):
    if value is None:
        return None

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")

    return value


def save_search_history(
    candidate,
    thread_id: str,
    keyword: str,
    location: str,
    ranked_jobs: list,
    selected_job: dict | None,
    application_materials=None,
    decision: str = "pending",
) -> int:
    profile_data = to_dict(candidate)

    if not isinstance(profile_data, dict):
        raise ValueError("Candidate profile must be a dictionary or Pydantic model.")

    name = profile_data.get("name", "Unknown Candidate")
    profile_key = name.strip().casefold()

    if not profile_key:
        raise ValueError("Candidate name cannot be empty.")

    if decision not in ("pending", "approved", "rejected"):
        raise ValueError("Invalid decision.")

    materials_data = to_dict(application_materials)

    with psycopg.connect(get_database_url()) as connection:
        candidate_row = connection.execute(
            """
            INSERT INTO candidate_profiles (
                profile_key, name, profile_data
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (profile_key)
            DO UPDATE SET
                name = EXCLUDED.name,
                profile_data = EXCLUDED.profile_data,
                updated_at = NOW()
            RETURNING candidate_id
            """,
            (profile_key, name, Jsonb(profile_data)),
        ).fetchone()

        candidate_id = candidate_row[0]

        run_row = connection.execute(
            """
            INSERT INTO job_search_runs (
                thread_id,
                candidate_id,
                keyword,
                location,
                decision,
                ranked_jobs,
                selected_job,
                application_materials
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (thread_id)
            DO UPDATE SET
                candidate_id = EXCLUDED.candidate_id,
                keyword = EXCLUDED.keyword,
                location = EXCLUDED.location,
                decision = EXCLUDED.decision,
                ranked_jobs = EXCLUDED.ranked_jobs,
                selected_job = EXCLUDED.selected_job,
                application_materials = EXCLUDED.application_materials,
                updated_at = NOW()
            RETURNING run_id
            """,
            (
                thread_id,
                candidate_id,
                keyword,
                location,
                decision,
                Jsonb(ranked_jobs),
                Jsonb(selected_job) if selected_job is not None else None,
                Jsonb(materials_data) if materials_data is not None else None,
            ),
        ).fetchone()

    return run_row[0]


def get_recent_search_history(limit: int = 10) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError("Limit must be between 1 and 100.")

    with psycopg.connect(get_database_url()) as connection:
        rows = connection.execute(
            """
            SELECT
                r.run_id,
                r.thread_id,
                c.name AS candidate_name,
                r.keyword,
                r.location,
                r.decision,
                r.ranked_jobs,
                r.selected_job,
                r.application_materials,
                r.created_at
            FROM job_search_runs AS r
            JOIN candidate_profiles AS c
                ON c.candidate_id = r.candidate_id
            ORDER BY r.updated_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()

    columns = [
        "run_id",
        "thread_id",
        "candidate_name",
        "keyword",
        "location",
        "decision",
        "ranked_jobs",
        "selected_job",
        "application_materials",
        "created_at",
    ]

    return [dict(zip(columns, row)) for row in rows]
