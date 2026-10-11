
import json
import sys
import uuid
from pathlib import Path

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from backend.database import get_database_url, get_recent_search_history
from backend.models.candidate import CandidateProfile
from backend.models.job import JobRequirements
from backend.models.application_materials import ApplicationMaterials
from backend.workflows.job_search_stage10_graph import build_stage10_graph


CV_PATH = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"

THREAD_FILE = Path("stage10_current_thread.txt")
SUMMARY_FILE = Path("stage10_history_summary.json")

SERDE = JsonPlusSerializer(
    allowed_msgpack_modules=[
        ("backend.models.candidate", "CandidateProfile"),
        ("backend.models.job", "JobRequirements"),
        ("backend.models.application_materials", "ApplicationMaterials"),
    ]
)


def start_workflow(graph):
    thread_id = f"stage11-{uuid.uuid4()}"
    THREAD_FILE.write_text(thread_id, encoding="utf-8")

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    result = graph.invoke(
        {
            "thread_id": thread_id,
            "cv_path": CV_PATH,
            "keyword": "AI machine learning",
            "location": "London",
            "results_per_page": 10,
            "preferences": {
                "location": "London",
                "remote_only": False,
                "min_salary": None,
                "excluded_keywords": [
                    "senior",
                    "lead",
                    "principal",
                ],
            },
        },
        config=config,
    )

    print("\nWorkflow started.")
    print(f"Thread ID: {thread_id}")

    if result.get("ranked_jobs"):
        top_job = result["ranked_jobs"][0]
        print(f"Top job: {top_job.get('job_title')}")
        print(f"Company: {top_job.get('company')}")
        print(f"Skill match score: {top_job.get('skill_match_score')}")
        print(f"Score status: {top_job.get('score_status')}")
        print("Workflow is waiting for your review.")
    else:
        print("No jobs remained after filtering and analysis.")
        print("Try broadening your preferences or searching another location.")


def resume_workflow(graph):
    if not THREAD_FILE.exists():
        print("No saved thread ID found. Run start first.")
        return

    thread_id = THREAD_FILE.read_text(encoding="utf-8").strip()

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    decision = input("Approve or reject the top job? ").strip().lower()

    if decision not in ("approve", "reject"):
        print("Enter only 'approve' or 'reject'.")
        return

    result = graph.invoke(
        Command(resume=decision),
        config=config,
    )

    print(f"\nReview decision: {decision}")

    if decision == "approve":
        materials = result.get("application_materials")

        if materials:
            if hasattr(materials, "model_dump"):
                materials = materials.model_dump()

            print("\nApplication materials generated:")
            print(json.dumps(materials, indent=2, ensure_ascii=False))
        else:
            print("The workflow resumed, but no materials were returned.")
    else:
        print("Job rejected. Application materials were not generated.")


def show_history():
    history = get_recent_search_history(limit=10)

    if not history:
        print("No search history found.")
        return

    print("\nRecent job search history:")

    for record in history:
        if hasattr(record, "model_dump"):
            record = record.model_dump()

        print(json.dumps(record, indent=2, default=str, ensure_ascii=False))

    SUMMARY_FILE.write_text(
        json.dumps(history, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nHistory summary written to: {SUMMARY_FILE}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m backend.test_stage10_integrated [start|resume|history]")
        return

    mode = sys.argv[1].strip().lower()

    if mode == "history":
        show_history()
        return

    if mode not in ("start", "resume"):
        print("Choose 'start', 'resume', or 'history'.")
        return

    with PostgresSaver.from_conn_string(
     get_database_url()
    ) as checkpointer:
        checkpointer.setup()
        graph = build_stage10_graph(checkpointer)

        if mode == "start":
            start_workflow(graph)
        else:
            resume_workflow(graph)


if __name__ == "__main__":
    from langgraph.types import Command
    main()
