
import json

from backend.tools.job_search import search_jobs
from backend.tools.cv_parser import extract_cv_text
from backend.tools.cv_analyzer import analyze_cv
from backend.tools.job_analyzer import analyze_job
from backend.tools.job_matcher import match_candidate_to_job, is_senior_role
from backend.tools.job_ranking import rank_jobs
from backend.tools.application_generator import generate_application_materials


CV_PATH = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"


def main():
    print("Analyzing CV...")

    cv_text = extract_cv_text(CV_PATH)
    candidate = analyze_cv(cv_text)

    print("CV analyzed successfully.")
    print("\nSearching for live jobs...")

    jobs = search_jobs(
        keyword="AI machine learning",
        location="London",
        results_per_page=10,
    )

    print(f"Jobs retrieved: {len(jobs)}")

    eligible_jobs = [
        job for job in jobs
        if not is_senior_role(job.get("title") or "")
    ]

    print(f"Jobs after senior-title filtering: {len(eligible_jobs)}")

    match_reports = []
    analyzed_jobs = []

    for index, job in enumerate(eligible_jobs, start=1):
        print(f"\nAnalyzing job {index}/{len(eligible_jobs)}:")
        print("Title:", job.get("title"))
        print("Company:", job.get("company"))

        try:
            requirements = analyze_job(job)
            report = match_candidate_to_job(candidate, requirements)

            match_reports.append(report)

            analyzed_jobs.append({
                "job": job,
                "requirements": requirements,
                "report": report,
            })

            print("Job analyzed successfully.")

        except Exception as error:
            print(
                f"Skipping job '{job.get('title', 'Unknown')}': {error}"
            )

    print(f"\nJobs successfully analyzed: {len(match_reports)}")

    if not match_reports:
        print("No jobs could be analyzed. Cannot generate materials.")
        return

    ranked_jobs = rank_jobs(match_reports)

    if not ranked_jobs:
        print("No ranked jobs are available.")
        return

    top_job = ranked_jobs[0]

    selected = next(
        (
            item for item in analyzed_jobs
            if (
                item["report"].get("job_title") == top_job.get("job_title")
                and item["report"].get("company") == top_job.get("company")
            )
        ),
        None,
    )

    if selected is None:
        print("Could not find the selected job's original requirements.")
        return

    print("\n" + "=" * 60)
    print("SELECTED JOB")
    print("=" * 60)
    print("Title:", top_job["job_title"])
    print("Company:", top_job["company"])
    print("Match score:", top_job["skill_match_score"])
    print("Match tier:", top_job["match_tier"])
    print("Score status:", top_job["score_status"])

    if top_job.get("warning"):
        print("Warning:", top_job["warning"])

    print("\nGenerating application materials...")

    try:
        materials = generate_application_materials(
            candidate=candidate,
            job=selected["requirements"],
            match_report=selected["report"],
        )
    except Exception as error:
        print(f"Application material generation failed: {error}")
        return

    print("\nAPPLICATION MATERIALS")
    print("=" * 60)
    print(materials.model_dump_json(indent=2))

    output_path = "stage5_application_materials.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(
            materials.model_dump(),
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nSaved materials to {output_path}")
    print("Review the generated content before using it.")


if __name__ == "__main__":
    main()