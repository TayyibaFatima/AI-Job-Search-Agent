
import json
import os
import sys

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Command

from backend.workflows.job_search_persistent_graph import (
    build_persistent_job_search_graph,
)


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
CV_PATH = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"

# Use the same thread ID for the start and resume commands.
THREAD_ID = "stage8-postgres-demo-001"


def main():
    if not DATABASE_URL:
        print("DATABASE_URL is missing from your .env file.")
        return

    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "resume"):
        print("Run one of these commands:")
        print("python -m backend.test_stage8_persistence start")
        print("python -m backend.test_stage8_persistence resume")
        return

    mode = sys.argv[1]

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

    try:
        with psycopg.connect(
            DATABASE_URL,
            autocommit=True,
            row_factory=dict_row,
        ) as connection:
            checkpointer = PostgresSaver(
                connection,
                serde=serializer,
            )

            # Creates or upgrades LangGraph's checkpoint tables.
            checkpointer.setup()

            graph = build_persistent_job_search_graph(checkpointer)

            if mode == "start":
                result = graph.invoke(
                    {
                        "cv_path": CV_PATH,
                        "keyword": "AI machine learning",
                        "location": "London",
                        "results_per_page": 5,
                    },
                    config=config,
                )

                interruptions = result.get("__interrupt__", [])

                if not interruptions:
                    print("Workflow did not reach the review step.")
                    if result.get("error"):
                        print("Reason:", result["error"])
                    return

                review = interruptions[0].value

                print("\nJOB CHECKPOINTED IN POSTGRESQL")
                print("Title:", review.get("job_title"))
                print("Company:", review.get("company"))
                print("Skill match:", review.get("skill_match_score"))
                print("Score status:", review.get("score_status"))

                if review.get("warning"):
                    print("Warning:", review["warning"])

                print("\nCheckpoint stored in PostgreSQL.")
                print("Close this program and run the resume command.")

            else:
                snapshot = graph.get_state(config)

                if not snapshot.values:
                    print("No saved workflow found for this thread.")
                    print("Run the start command first.")
                    return

                if not snapshot.next:
                    print("This workflow has already finished.")
                    print("Use a new THREAD_ID to run a fresh test.")
                    return

                if "review_job" not in snapshot.next:
                    print("The saved workflow is not waiting for job review.")
                    print("Use a new THREAD_ID to run a fresh test.")
                    return

                print("Restored the saved job review from PostgreSQL.")
                decision = input(
                    "Enter approve or reject: "
                ).strip().lower()

                while decision not in ("approve", "reject"):
                    decision = input(
                        "Enter only approve or reject: "
                    ).strip().lower()

                result = graph.invoke(
                    Command(resume=decision),
                    config=config,
                )

                if decision == "reject":
                    print("\nJob rejected.")
                    print("Application materials were not generated.")
                    return

                if result.get("error"):
                    print("\nWorkflow error:", result["error"])
                    return

                materials = result.get("application_materials")

                if materials is None:
                    print("Application materials were not generated.")
                    return

                print("\nAPPLICATION MATERIALS")
                print(materials.model_dump_json(indent=2))

                with open(
                    "stage8_application_materials.json",
                    "w",
                    encoding="utf-8",
                ) as file:
                    json.dump(
                        materials.model_dump(),
                        file,
                        indent=2,
                        ensure_ascii=False,
                    )

                print("\nSaved stage8_application_materials.json")
                print("PostgreSQL persistence test passed.")

    except Exception as error:
        print("\nStage 8 error:", error)
        print(
            "Check that PostgreSQL is running, the database exists, "
            "and DATABASE_URL has the correct credentials."
        )
        raise


if __name__ == "__main__":
    main()
