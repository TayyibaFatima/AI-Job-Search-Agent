
import json

from backend.workflows.job_search_graph import job_search_graph


CV_PATH = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"


def main():
    print("=" * 60)
    print("STAGE 6: LANGGRAPH JOB SEARCH WORKFLOW")
    print("=" * 60)

    result = job_search_graph.invoke({
        "cv_path": CV_PATH,
        "keyword": "AI machine learning",
        "location": "London",
        "results_per_page": 5,
    })

    if result.get("error"):
        print("\nWorkflow stopped:", result["error"])
        return

    ranked_jobs = result.get("ranked_jobs", [])

    if not ranked_jobs:
        print("\nNo ranked jobs are available.")
        return

    top_job = ranked_jobs[0]
    materials = result.get("application_materials")

    if materials is None:
        print("\nApplication materials were not generated.")
        return

    print("\n" + "=" * 60)
    print("WORKFLOW RESULTS")
    print("=" * 60)

    print("Jobs retrieved:", len(result.get("jobs", [])))
    print("Jobs analyzed:", len(result.get("match_reports", [])))
    print("Jobs ranked:", len(ranked_jobs))

    print("\nTOP-RANKED JOB")
    print("Title:", top_job["job_title"])
    print("Company:", top_job["company"])
    print("Skill match:", top_job["skill_match_score"])
    print("Match tier:", top_job["match_tier"])
    print("Score status:", top_job["score_status"])

    if top_job.get("warning"):
        print("Warning:", top_job["warning"])

    print("\nSKILL GAPS")
    for gap in result.get("skill_gaps", []):
        print(
            f"- {gap['skill']}: "
            f"missing across {gap['frequency']} job(s)"
        )

    print("\nAPPLICATION MATERIALS")
    print(materials.model_dump_json(indent=2))

    output = {
        "jobs_retrieved": len(result.get("jobs", [])),
        "jobs_analyzed": len(result.get("match_reports", [])),
        "ranked_jobs": ranked_jobs,
        "skill_gaps": result.get("skill_gaps", []),
        "selected_job": top_job,
        "application_materials": materials.model_dump(),
    }

    output_path = "stage6_workflow_output.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nWorkflow results saved to {output_path}")
    print("Stage 6 workflow completed successfully.")


if __name__ == "__main__":
    main()
