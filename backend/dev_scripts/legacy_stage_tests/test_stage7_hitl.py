
import json

from langgraph.types import Command

from backend.workflows.job_search_hitl_graph import (
    job_search_hitl_graph,
)


CV_PATH = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"


def main():
    print("=" * 60)
    print("STAGE 7: HUMAN-IN-THE-LOOP APPROVAL")
    print("=" * 60)

    config = {
        "configurable": {
            "thread_id": "stage7-review-session"
        }
    }

    initial_state = {
        "cv_path": CV_PATH,
        "keyword": "AI machine learning",
        "location": "London",
        "results_per_page": 5,
    }

    print("\nStarting workflow...")

    result = job_search_hitl_graph.invoke(
        initial_state,
        config=config,
    )

    interruptions = result.get("__interrupt__", [])

    if not interruptions:
        print("\nWorkflow stopped before the review step.")

        if result.get("error"):
            print("Reason:", result["error"])
        else:
            print("No suitable jobs were available for review.")

        return

    review = interruptions[0].value

    print("\n" + "=" * 60)
    print("JOB REVIEW REQUIRED")
    print("=" * 60)
    print("Title:", review.get("job_title"))
    print("Company:", review.get("company"))
    print("Skill match:", review.get("skill_match_score"))
    print("Match tier:", review.get("match_tier"))
    print("Score status:", review.get("score_status"))

    if review.get("missing_required_skills"):
        print(
            "Missing required skills:",
            ", ".join(review["missing_required_skills"]),
        )

    if review.get("warning"):
        print("Warning:", review["warning"])

    print("\nThis score measures skill overlap, not overall suitability.")
    print("Review the job details before deciding.")
    print("\n1. Approve — generate application materials")
    print("2. Reject — stop without generating materials")

    choice = input("\nEnter approve or reject: ").strip().lower()

    while choice not in ("approve", "reject"):
        choice = input(
            "Please enter only 'approve' or 'reject': "
        ).strip().lower()

    print("\nResuming workflow...")

    result = job_search_hitl_graph.invoke(
        Command(resume=choice),
        config=config,
    )

    if choice == "reject":
        print("\nJob rejected.")
        print("Application materials were not generated.")
        print("Stage 7 rejection test completed.")
        return

    if result.get("error"):
        print("\nWorkflow error:", result["error"])
        return

    materials = result.get("application_materials")

    if materials is None:
        print("\nApplication materials were not generated.")
        return

    print("\n" + "=" * 60)
    print("APPROVED: APPLICATION MATERIALS")
    print("=" * 60)
    print(materials.model_dump_json(indent=2))

    output = {
        "selected_job": result["ranked_jobs"][0],
        "application_materials": materials.model_dump(),
    }

    output_path = "stage7_approved_application.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=2, ensure_ascii=False)

    print(f"\nSaved results to {output_path}")
    print("Stage 7 approval test completed successfully.")
    print("Review all generated content before using it.")


if __name__ == "__main__":
    main()
