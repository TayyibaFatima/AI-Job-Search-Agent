from backend.tools.skill_taxonomy import normalize_skill


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


def get_match_tier(
    score: float | None,
    confidence: str = "medium",
) -> str:
    """Describe skill overlap without implying hiring probability."""

    if score is None:
        return "Insufficient data"

    if confidence == "low":
        return "Low-confidence estimate"

    if score >= 80:
        return "Strong skill overlap"

    if score >= 50:
        return "Moderate skill overlap"

    return "Low skill overlap"


CONFIDENCE_ORDER = {"high": 2, "medium": 1, "low": 0}


def rank_jobs(match_reports: list[dict]) -> list[dict]:
    """
    Rank jobs by a confidence-adjusted skill-overlap score.

    The adjusted ``ranking_score`` shrinks small samples toward 50%, so a
    listing with one extracted skill cannot outrank a well-evidenced one.
    Jobs without any score appear last. Ties favour higher confidence and
    then listings with more extracted requirements.
    """

    ranked = []

    for report in match_reports:
        item = report.copy()
        item["match_tier"] = get_match_tier(
            item.get("skill_match_score"),
            item.get("confidence", "medium"),
        )
        ranked.append(item)

    def sort_key(item):
        score = item.get("ranking_score")
        return (
            score is not None,
            score if score is not None else -1,
            CONFIDENCE_ORDER.get(item.get("confidence"), 0),
            item.get("total_required_skills", 0),
            str(item.get("job_title", "")).lower(),  # stable tie-break
        )

    ranked.sort(key=sort_key, reverse=True)

    for position, job in enumerate(ranked, start=1):
        job["rank"] = position

    return ranked
