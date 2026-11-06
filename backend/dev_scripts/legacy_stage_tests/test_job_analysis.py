from backend.tools.job_ranking import (
    analyze_skill_gaps,
    rank_jobs,
)
import json
from backend.tools.job_search import search_jobs
from backend.tools.cv_parser import extract_cv_text
from backend.tools.cv_analyzer import analyze_cv
from backend.tools.job_analyzer import analyze_job
from backend.tools.job_matcher import (
    match_candidate_to_job,
    is_senior_role,
)


cv_path = r"C:\Users\Tayyiba\Desktop\Syeda_Tayyiba_Fatima.pdf"


print("Analyzing CV...")

cv_text = extract_cv_text(cv_path)
candidate = analyze_cv(cv_text)


print("\nSearching live jobs...")

jobs = search_jobs(
    keyword="AI machine learning",
    location="London",
    results_per_page=10
)

print(f"Retrieved {len(jobs)} live jobs.")

eligible_jobs = []

for job in jobs:
    title = job.get("title") or ""

    if is_senior_role(title):
        print(f"Skipping senior role: {title}")
    else:
        eligible_jobs.append(job)

print(
    f"\nJobs remaining after senior-title filtering: "
    f"{len(eligible_jobs)}"
)

match_reports = []
for index, job in enumerate(eligible_jobs, start=1):
    print("\n" + "=" * 60)
    print(f"JOB {index}: {job.get('title')}")
    print("Company:", job.get("company"))

    try:
        requirements = analyze_job(job)

        result = match_candidate_to_job(
            candidate,
            requirements
        )
        match_reports.append(result)
        print("\nJOB REQUIREMENTS")
        print(requirements.model_dump_json(indent=2))

        print("\nMATCH REPORT")
        print(json.dumps(result, indent=2))

        print("\nSeniority note:")
        print(
            "This title passed the senior-title filter. "
            "It is not confirmed to be entry-level; "
            "check the full listing."
        )

    except Exception as error:
        print(f"Could not analyze this job: {error}")
    print("\n" + "=" * 60)
print("STAGE 4: RANKED JOBS")
print("=" * 60)

ranked_jobs = rank_jobs(match_reports)

for job in ranked_jobs:
    print(f"\nRank: #{job['rank']}")
    print(f"Job: {job['job_title']}")
    print(f"Company: {job['company']}")
    print(f"Skill match: {job['skill_match_score']}")
    print(f"Match tier: {job['match_tier']}")
    print(f"Score status: {job['score_status']}")

    if job.get("warning"):
        print(f"Warning: {job['warning']}")


print("\n" + "=" * 60)
print("STAGE 4: SKILL-GAP ANALYSIS")
print("=" * 60)

skill_gaps = analyze_skill_gaps(match_reports)

if not skill_gaps:
    print("No missing required skills were identified.")
else:
    for gap in skill_gaps:
        print(f"\nSkill: {gap['skill']}")
        print(f"Missing across {gap['frequency']} job(s):")

        for job_label in gap["jobs"]:
            print(f"  - {job_label}")