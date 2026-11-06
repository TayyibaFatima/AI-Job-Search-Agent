
import os
import json

import psycopg
from dotenv import load_dotenv

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from backend.database import (
    setup_application_tables,
    save_search_history,
    get_recent_search_history,
)
from backend.workflows.job_search_persistent_graph import (
    build_persistent_job_search_graph,
)


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
THREAD_ID = "stage8-postgres-demo-001"


def main():
    if not DATABASE_URL:
        print("DATABASE_URL is missing from .env.")
        return

    print("=" * 60)
    print("STAGE 9: POSTGRESQL APPLICATION HISTORY")
    print("=" * 60)

    setup_application_tables()

    serializer = JsonPlusSerializer(
        allowed_msgpack_modules=[
            ("backend.models.candidate", "CandidateProfile"),
            ("backend.models.job", "JobRequirements"),
            (
                "backend.models.application_materials",
                "ApplicationMaterials",
            ),
        ]
    )

    config = {
        "configurable": {
            "thread_id": THREAD_ID,
        }
    }

    with psycopg.connect(
        DATABASE_URL,
        autocommit=True,
    ) as connection:
        checkpointer = PostgresSaver(
            connection,
            serde=serializer,
        )
        checkpointer.setup()

        graph = build_persistent_job_search_graph(checkpointer)
        snapshot = graph.get_state(config)

        if not snapshot.values:
            print("No saved Stage 8 workflow was found.")
            print("Run Stage 8 start and resume successfully first.")
            return

        state = snapshot.values
        candidate = state.get("candidate")
        ranked_jobs = state.get("ranked_jobs", [])
        materials = state.get("application_materials")

        if candidate is None or not ranked_jobs:
            print("The saved workflow is missing candidate or job data.")
            return

        selected_job = ranked_jobs[0]
        decision = state.get("human_decision")

        if decision == "approve":
           decision = "approved"
        elif decision == "reject":
          decision = "rejected"
        elif decision not in ("approved", "rejected"):
          decision = (
           "approved" if materials is not None else "pending"
        )

        run_id = save_search_history(
            candidate=candidate,
            thread_id=THREAD_ID,
            keyword="AI machine learning",
            location="London",
            ranked_jobs=ranked_jobs,
            selected_job=selected_job,
            application_materials=materials,
            decision=decision,
        )

    print("\nSaved workflow history.")
    print("History record ID:", run_id)
    print("Candidate:", candidate.name)
    print("Ranked jobs stored:", len(ranked_jobs))
    print("Decision:", decision)

    history = get_recent_search_history(limit=5)

    print("\nRECENT SEARCH HISTORY")
    for item in history:
        print("-" * 40)
        print("Run ID:", item["run_id"])
        print("Candidate:", item["candidate_name"])
        print("Search:", item["keyword"])
        print("Location:", item["location"])
        print("Decision:", item["decision"])
        print(
            "Stored ranked jobs:",
            len(item["ranked_jobs"] or []),
        )

    with open(
        "stage9_history_summary.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            [
                {
                    "run_id": item["run_id"],
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

    print("\nSaved summary to stage9_history_summary.json")
    print("Stage 9 database history test completed.")


if __name__ == "__main__":
    main()
