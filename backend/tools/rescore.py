"""Re-score one job from a description the user pasted in."""

from backend.tools.job_analyzer import analyze_job
from backend.tools.job_matcher import match_candidate_to_job
from backend.tools.job_ranking import analyze_skill_gaps, rank_jobs

# Report fields that come from the job listing, not from scoring.
PASSTHROUGH_FIELDS = (
    "redirect_url",
    "location",
    "salary_min",
    "salary_max",
    "contract_type",
    "source",
    "source_label",
    "salary_text",
)


def find_analyzed_job(state: dict, job_index: int) -> tuple[int, dict]:
    """Return (position, item) in ``analyzed_jobs`` for a ranked job index.

    If two listings share a title and company, the matching occurrence is used.
    Raises LookupError when the job cannot be found.
    """
    ranked_jobs = state.get("ranked_jobs", [])
    if job_index < 0 or job_index >= len(ranked_jobs):
        raise LookupError("That job is not in this search.")

    job = ranked_jobs[job_index]
    occurrence = sum(
        1
        for earlier in ranked_jobs[:job_index]
        if earlier.get("job_title") == job.get("job_title")
        and earlier.get("company") == job.get("company")
    )
    matches = [
        (position, item)
        for position, item in enumerate(state.get("analyzed_jobs", []))
        if item["report"].get("job_title") == job.get("job_title")
        and item["report"].get("company") == job.get("company")
    ]
    if not matches:
        raise LookupError("Could not find the original requirements for this job.")

    return matches[min(occurrence, len(matches) - 1)]


def rescore_job(state: dict, job_index: int, description: str) -> dict:
    """Analyze a pasted description and return the updated state values."""
    position, item = find_analyzed_job(state, job_index)

    job = {
        **item["job"],
        "description": description.strip(),
        "description_source": "pasted",
    }
    requirements = analyze_job(job)
    report = match_candidate_to_job(state["candidate"], requirements)
    for field in PASSTHROUGH_FIELDS:
        report[field] = item["report"].get(field)

    analyzed_jobs = list(state["analyzed_jobs"])
    analyzed_jobs[position] = {
        "job": job,
        "requirements": requirements,
        "report": report,
    }
    match_reports = [entry["report"] for entry in analyzed_jobs]

    return {
        "analyzed_jobs": analyzed_jobs,
        "match_reports": match_reports,
        "ranked_jobs": rank_jobs(match_reports),
        "skill_gaps": analyze_skill_gaps(match_reports),
    }
