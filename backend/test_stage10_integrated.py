
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import load_dotenv

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command

from backend.database import get_recent_search_history
from backend.workflows.job_search_stage10_graph import build_stage10_graph


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
CV_PATH = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"

THREAD_FILE = Path("stage10_current_thread.txt")


def create_serializer():
    return JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("backend.models.candidate", "CandidateProfile"),
            ("backend.models.job", "JobRequirements"),
            (
                "backend.models.application_materials",
                "ApplicationMaterials",
            ),
        ]
    )


def show_history():
    history = get_recent_search_history(limit=10)

    print("\nRECENT POSTGRESQL SEARCH HISTORY")
    print("=" * 60)

    if not history:
        print("No search history found.")
        return

    for item in history:
        print("-" * 40)
        print("Run ID:", item["run_id"])
        print("Thread:", item["thread_id"])
        print("Candidate:", item["candidate_name"])
        print("Search:", item["keyword"])
        print("Location:", item["location"])
        print("Decision:", item["decision"])
        print("Ranked jobs:", len(item["ranked_jobs"] or []))

    with open(
        "stage10_history_summary.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            [
                {
                    "run_id": item["run_id"],
                    "thread_id": item["thread_id"],
                    "candidate_name": item["candidate_name"],
                    "keyword": item["keyword"],
                    "location": item["location"],
                    "decision": item["decision"],
                    "ranked_jobs_count": len(
                        item["ranked_jobs"] or []
                    ),
                    "created_at": item["created_at"].isoformat(),
                }
                for item in history
            ],
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("\nHistory summary saved to stage10_history_summary.json")


def main():
    if not DATABASE_URL:
        print("DATABASE_URL is missing from your .env file.")
        return

    if len(sys.argv) != 2 or sys.argv[1] not in (
        "start",
        "resume",
        "history",
    ):
        print("Usage:")
        print("python -m backend.test_stage10_integrated start")
        print("python -m backend.test_stage10_integrated resume")
        print("python -m backend.test_stage10_integrated history")
        return

    mode = sys.argv[1]

    if mode == "history":
        show_history()
        return

    if mode == "start":
        thread_id = f"stage10-{uuid4()}"
        THREAD_FILE.write_text(thread_id, encoding="utf-8")
    else:
        if not THREAD_FILE.exists():
            print("No Stage 10 session found. Run start first.")
            return

        thread_id = THREAD_FILE.read_text(
            encoding="utf-8"
        ).strip()

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    print("Stage 10 thread ID:", thread_id)

    try:
        with psycopg.connect(
            DATABASE_URL,
            autocommit=True,
        ) as connection:
            checkpointer = PostgresSaver(
                connection,
                serde=create_serializer(),
            )
            checkpointer.setup()

            graph = build_stage10_graph(checkpointer)

            if mode == "start":
                result = graph.invoke(
                    {
                        "thread_id": thread_id,
                        "cv_path": CV_PATH,
                        "keyword": "AI machine learning",
                        "location": "London",
                        "results_per_page": 5,
                    },
                    config=config,
                )

                interruptions = result.get("__interrupt__", [])

                if not interruptions:
                    print("Workflow did not reach job review.")
                    if result.get("error"):
                        print("Reason:", result["error"])
                    return

                review = interruptions[0].value

                print("\nJOB REVIEW")
                print("Title:", review.get("job_title"))
                print("Company:", review.get("company"))
                print("Skill match:", review.get("skill_match_score"))
                print("Score status:", review.get("score_status"))

                if review.get("warning"):
                    print("Warning:", review["warning"])

                print("\nCandidate and job ranking saved to PostgreSQL.")
                print("Run the resume command to approve or reject.")

            else:
                snapshot = graph.get_state(config)

                if not snapshot.values:
                    print("No saved workflow found for this session.")
                    return

                if "review_job" not in snapshot.next:
                    print("This session is not waiting for job review.")
                    print("Check its result with the history command.")
                    return

                decision = input(
                    "\nEnter approve or reject: "
                ).strip().lower()

                while decision not in ("approve", "reject"):
                    decision = input(
                        "Enter only approve or reject: "
                    ).strip().lower()

                result = graph.invoke(
                    Command(resume=decision),
                    config=config,
                )

                print(
                    "\nDecision recorded:",
                    "approved" if decision == "approve" else "rejected",
                )

                if decision == "reject":
                    print("No application materials were generated.")
                else:
                    materials = result.get("application_materials")

                    if materials is None:
                        print("Application materials were not generated.")
                    else:
                        print("\nApplication materials saved to PostgreSQL.")
                        print(materials.model_dump_json(indent=2))

                print("\nRun this to inspect saved searches:")
                print("python -m backend.test_stage10_integrated history")

    except Exception as error:
        print("\nStage 10 failed:", error)
        raise


if __name__ == "__main__":
    main()
