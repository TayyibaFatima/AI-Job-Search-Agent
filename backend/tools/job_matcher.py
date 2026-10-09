import re

from backend.models.candidate import CandidateProfile
from backend.models.job import JobRequirements


SKILL_ALIASES = {
    "ml": "machine learning",
    "machine-learning": "machine learning",
    "llm": "large language models",
    "llms": "large language models",
    "large language model": "large language models",
    "postgres": "postgresql",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "rest api": "rest apis",
    "restful api": "rest apis",
    "artificial intelligence": "ai",
}


RELATED_EVIDENCE = {
    "machine learning": [
        "scikit-learn",
        "neural network",
        "classification",
        "classifier",
    ],
    "generative ai": [
        "large language model",
        "llm api",
        "llm-powered",
    ],
    "large language models": [
        "generative ai",
        "llm api",
    ],
}


def normalize_skill(skill: str) -> str:
    normalized = skill.lower().strip()
    normalized = normalized.replace("_", " ")
    normalized = normalized.replace(" (llms)", "")
    normalized = re.sub(r"[^a-z0-9+#.\s-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return SKILL_ALIASES.get(normalized, normalized)


def expand_skill(skill: str) -> list[str]:
    """Split combined skill labels into separate requirements."""

    normalized = skill.strip()

    if re.search(r"\s*&\s*|\s*/\s*", normalized):
        parts = re.split(r"\s*&\s*|\s*/\s*", normalized)

    elif re.fullmatch(
        r"AI\s+and\s+Machine Learning",
        normalized,
        re.IGNORECASE,
    ):
        parts = re.split(
            r"\s+and\s+",
            normalized,
            flags=re.IGNORECASE,
        )

    else:
        parts = [normalized]

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def collect_candidate_evidence(
    candidate: CandidateProfile,
) -> list[str]:
    evidence = list(candidate.skills)

    for project in candidate.projects:
        evidence.append(project.name)
        evidence.extend(project.technologies)
        evidence.append(project.description)

    for experience in candidate.experience:
        evidence.append(experience.role)
        evidence.append(experience.organization)
        evidence.append(experience.description)

    for education in candidate.education:
        evidence.append(education.degree)
        evidence.append(education.institution)
        evidence.append(education.field)

    return [
        item.strip()
        for item in evidence
        if item and item.strip()
    ]


def contains_phrase(text: str, phrase: str) -> bool:
    pattern = (
        r"(?<![a-z0-9+#])"
        + re.escape(phrase.lower())
        + r"(?![a-z0-9+#])"
    )

    return bool(re.search(pattern, text.lower()))


def has_skill_evidence(
    required_skill: str,
    evidence: list[str],
) -> bool:
    target = normalize_skill(required_skill)

    normalized_evidence = [
        normalize_skill(item)
        for item in evidence
    ]

    # Direct skill match.
    if target in normalized_evidence:
        return True

    # Direct phrase match in CV projects, experience, and other evidence.
    for item in evidence:
        if contains_phrase(item, target):
            return True

    # Related evidence can support a broader skill match.
    related_terms = RELATED_EVIDENCE.get(target, [])

    for term in related_terms:
        for item in evidence:
            if contains_phrase(item, term):
                return True

    return False


def is_senior_role(job_title: str) -> bool:
    pattern = (
        r"\b("
        r"senior|sr\.?|lead|principal|director|"
        r"head of|chief|vice president|vp|"
        r"staff engineer|engineering manager|"
        r"technical manager"
        r")\b"
    )

    return bool(re.search(pattern, job_title, re.IGNORECASE))


def match_candidate_to_job(
    candidate: CandidateProfile,
    job: JobRequirements,
) -> dict:
    evidence = collect_candidate_evidence(candidate)

    required = list(dict.fromkeys(
        skill
        for item in job.required_skills
        for skill in expand_skill(item)
    ))

    preferred = list(dict.fromkeys(
        skill
        for item in job.preferred_skills
        for skill in expand_skill(item)
    ))

    matched_required = [
        skill
        for skill in required
        if has_skill_evidence(skill, evidence)
    ]

    missing_required = [
        skill
        for skill in required
        if not has_skill_evidence(skill, evidence)
    ]

    matched_preferred = [
        skill
        for skill in preferred
        if has_skill_evidence(skill, evidence)
    ]

    match_score = (
        round(len(matched_required) / len(required) * 100, 2)
        if required
        else None
    )

    if match_score is None:
        score_status = "unavailable"
    elif (
        job.description_quality != "good"
        or job.missing_information
    ):
        score_status = "preliminary"
    else:
        score_status = "based_on_available_requirements"

    return {
        "job_title": job.job_title,
        "company": job.company,
        "skill_match_score": match_score,
        "score_status": score_status,
        "description_quality": job.description_quality,
        "matched_required_skills": matched_required,
        "missing_required_skills": missing_required,
        "matched_preferred_skills": matched_preferred,
        "total_required_skills": len(required),
        "total_matched_required_skills": len(matched_required),
        "missing_information": job.missing_information,
        "interpretation": (
            f"{len(matched_required)} of {len(required)} "
            "extracted required skills matched. "
            "This score does not measure overall suitability."
            if required
            else "No required skills could be extracted, so "
                 "a skill match score is unavailable."
        ),
        "warning": (
            "Job description is incomplete. Verify the full "
            "listing before relying on this result."
            if (
                job.description_quality != "good"
                or job.missing_information
            )
            else None
        ),
    }

