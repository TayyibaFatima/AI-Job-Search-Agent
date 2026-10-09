from backend.tools.job_matcher import normalize_skill


def analyze_skill_gaps(match_reports: list[dict]) -> list[dict]:
    """
    Find required skills missing from the candidate's CV
    across the analyzed job listings.
    """

    skill_gaps = {}

    for report in match_reports:
        job_title = report.get("job_title", "Unknown title")
        company = report.get("company", "Unknown company")

        for skill in report.get("missing_required_skills", []):
            normalized = normalize_skill(skill)

            if not normalized:
                continue

            if normalized not in skill_gaps:
                skill_gaps[normalized] = {
                    "skill": skill,
                    "frequency": 0,
                    "jobs": [],
                }

            job_label = f"{job_title} — {company}"

            # Count each job only once per skill.
            if job_label not in skill_gaps[normalized]["jobs"]:
                skill_gaps[normalized]["frequency"] += 1
                skill_gaps[normalized]["jobs"].append(job_label)

    return sorted(
        skill_gaps.values(),
        key=lambda item: (
            -item["frequency"],
            item["skill"].lower(),
        ),
    )


def get_match_tier(score: float | None) -> str:
    """Describe skill overlap without implying hiring probability."""

    if score is None:
        return "Insufficient data"

    if score >= 80:
        return "Strong skill overlap"

    if score >= 50:
        return "Moderate skill overlap"

    return "Low skill overlap"


def rank_jobs(match_reports: list[dict]) -> list[dict]:
    """
    Rank jobs by extracted required-skill overlap.

    Jobs without a score appear last. Ties favor more complete
    descriptions and then listings with more extracted requirements.
    """

    ranked = []

    for report in match_reports:
        item = report.copy()

        score = item.get("skill_match_score")
        item["match_tier"] = get_match_tier(score)

        ranked.append(item)

    ranked.sort(
        key=lambda item: (
            item.get("skill_match_score") is not None,
            (
                item.get("skill_match_score")
                if item.get("skill_match_score") is not None
                else -1
            ),
            item.get("description_quality") == "good",
            item.get("total_required_skills", 0),
        ),
        reverse=True,
    )

    for position, job in enumerate(ranked, start=1):
        job["rank"] = position

    return ranked