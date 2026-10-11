
from typing import Any


def filter_jobs(
    jobs: list[dict[str, Any]],
    location: str | None = None,
    remote_only: bool = False,
    min_salary: float | None = None,
    excluded_keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Filter job listings using the candidate's explicit preferences."""

    filtered_jobs = []

    excluded = [
        keyword.strip().casefold()
        for keyword in (excluded_keywords or [])
        if keyword.strip()
    ]

    for job in jobs:
        title = str(job.get("title") or "")
        company = str(job.get("company") or "")
        job_location = str(job.get("location") or "")
        description = str(job.get("description") or "")

        searchable_text = (
            f"{title} {company} {job_location} {description}"
        ).casefold()

        # Exclude jobs containing unwanted keywords.
        if any(keyword in searchable_text for keyword in excluded):
            continue

        # Keep jobs whose listed location matches the requested location.
        if location:
            requested_location = location.strip().casefold()

            if requested_location not in job_location.casefold():
                continue

        # Keep only listings that explicitly indicate remote work.
        if remote_only:
            remote_text = (
                f"{title} {job_location} {description}"
            ).casefold()

            remote_indicators = [
                "remote",
                "work from home",
                "work-from-home",
                "fully distributed",
            ]

            if not any(term in remote_text for term in remote_indicators):
                continue

        # Exclude jobs when salary information is missing or below the minimum.
        if min_salary is not None:
            salary_min = job.get("salary_min")
            salary_max = job.get("salary_max")

            try:
                lower = float(salary_min) if salary_min is not None else None
                upper = float(salary_max) if salary_max is not None else None
            except (TypeError, ValueError):
                continue

            known_salary = upper if upper is not None else lower

            if known_salary is None or known_salary < min_salary:
                continue

        filtered_jobs.append(job)

    return filtered_jobs
