"""
Candidate <-> job skill matching.

Scoring model
-------------
* Every required skill is classed as a DIRECT match (the CV names it),
  a RELATED match (the CV shows closely related tools, worth half credit)
  or MISSING.
* ``skill_match_score``  = (direct + 0.5 * related) / required * 100
* ``confidence`` reflects how much evidence the score rests on. A score
  built from 1 or 2 skills is flagged "low" and is never presented as a
  confident result; with zero skills the score is simply unavailable.
* ``ranking_score`` shrinks small samples toward 50% so that "1 of 1" can
  not outrank "8 of 10". It is used only for ordering.
"""

from __future__ import annotations

import re

from backend.models.candidate import CandidateProfile
from backend.models.job import JobRequirements
from backend.tools.skill_taxonomy import (
    SKILLS,
    contains_phrase,
    find_skills,
    normalize_skill,
)

MIN_SKILLS_FOR_CONFIDENT_SCORE = 3
HIGH_CONFIDENCE_MIN_SKILLS = 5
RELATED_CREDIT = 0.5
RANKING_PRIOR_WEIGHT = 3  # pseudo-skills at 50% used to shrink small samples

# required skill -> skills that give related (partial) evidence for it
RELATED_EVIDENCE: dict[str, list[str]] = {
    "machine learning": [
        "scikit-learn", "pytorch", "tensorflow", "keras", "xgboost",
        "neural networks", "deep learning", "natural language processing",
        "computer vision",
    ],
    "ai": [
        "machine learning", "deep learning", "generative ai",
        "large language models", "natural language processing",
        "computer vision", "neural networks",
    ],
    "deep learning": ["pytorch", "tensorflow", "keras", "neural networks"],
    "generative ai": [
        "large language models", "rag", "prompt engineering", "langchain",
    ],
    "large language models": [
        "generative ai", "openai api", "langchain", "rag", "hugging face",
    ],
    "data analysis": ["pandas", "data science", "excel", "power bi", "tableau"],
    "sql": ["postgresql", "mysql", "sqlite"],
    "nosql": ["mongodb", "redis"],
    "rest apis": ["fastapi", "flask", "django", "api integration"],
    "api integration": ["rest apis"],
    "automation": ["n8n", "zapier", "selenium"],
    "docker": ["kubernetes"],
    "git": ["github actions"],
}


def expand_skill(skill: str) -> list[str]:
    """Split combined labels such as 'AI & Machine Learning' into parts."""
    text = (skill or "").strip()

    if normalize_skill(text) in SKILLS:
        # Real skills such as "ci/cd" must stay in one piece.
        parts = [text]
    elif re.search(r"\s*&\s*|\s*/\s*", text):
        parts = re.split(r"\s*&\s*|\s*/\s*", text)
    elif re.fullmatch(r"AI\s+and\s+Machine Learning", text, re.IGNORECASE):
        parts = re.split(r"\s+and\s+", text, flags=re.IGNORECASE)
    else:
        parts = [text]

    return [p.strip() for p in parts if p.strip()]


def collect_candidate_evidence(candidate: CandidateProfile) -> list[str]:
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

    return [item.strip() for item in evidence if item and item.strip()]


def build_candidate_skill_set(evidence: list[str]) -> tuple[set[str], str]:
    """Canonical skills the CV demonstrates, plus the joined evidence text."""
    blob = "\n".join(evidence)

    skills = {normalize_skill(item) for item in evidence}
    skills.update(find_skills(blob))
    skills.discard("")

    return skills, blob


def classify_skill(
    required_skill: str,
    candidate_skills: set[str],
    evidence_blob: str,
) -> str | None:
    """Return 'direct', 'related' or None for one required skill."""
    target = normalize_skill(required_skill)

    if target in candidate_skills or contains_phrase(evidence_blob, target):
        return "direct"

    for related in RELATED_EVIDENCE.get(target, []):
        if related in candidate_skills:
            return "related"

    return None


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


def _unique(skills) -> list[str]:
    return list(dict.fromkeys(skills))


def compute_confidence(total: int, quality: str, source: str) -> str:
    if total < MIN_SKILLS_FOR_CONFIDENT_SCORE:
        return "low"

    if (
        total >= HIGH_CONFIDENCE_MIN_SKILLS
        and quality == "good"
        and source == "full_page"
    ):
        return "high"

    return "medium"


def match_candidate_to_job(
    candidate: CandidateProfile,
    job: JobRequirements,
) -> dict:
    evidence = collect_candidate_evidence(candidate)
    candidate_skills, blob = build_candidate_skill_set(evidence)

    required = _unique(
        normalize_skill(skill)
        for item in job.required_skills
        for skill in expand_skill(item)
    )
    preferred = [
        skill
        for skill in _unique(
            normalize_skill(skill)
            for item in job.preferred_skills
            for skill in expand_skill(item)
        )
        if skill not in required
    ]

    direct, related, missing = [], [], []
    for skill in required:
        kind = classify_skill(skill, candidate_skills, blob)
        (direct if kind == "direct" else related if kind == "related"
         else missing).append(skill)

    matched_preferred = [
        skill for skill in preferred
        if classify_skill(skill, candidate_skills, blob) == "direct"
    ]

    total = len(required)
    points = len(direct) + RELATED_CREDIT * len(related)

    score = round(points / total * 100, 1) if total else None
    ranking_score = (
        round(
            (points + RANKING_PRIOR_WEIGHT * 0.5)
            / (total + RANKING_PRIOR_WEIGHT) * 100,
            1,
        )
        if total
        else None
    )

    confidence = compute_confidence(
        total, job.description_quality, job.description_source
    )

    if total == 0:
        status = "insufficient_data"
    elif confidence == "low":
        status = "low_confidence"
    else:
        status = "scored"

    if total == 0:
        interpretation = (
            "No technical skills could be identified in this listing, so a "
            "skill match score is unavailable."
        )
    else:
        parts = [f"{len(direct)} of {total} listed skills found on your CV"]
        if related:
            parts.append(f"{len(related)} partly covered by related experience")
        interpretation = (
            "; ".join(parts) + ". This measures skill overlap only, "
            "not overall suitability."
        )

    warnings = []
    if job.description_source != "full_page":
        warnings.append(
            "Based on a short preview of the listing. Open the listing to "
            "check for requirements not shown here."
        )
    if 0 < total < MIN_SKILLS_FOR_CONFIDENT_SCORE:
        warnings.append(
            f"Only {total} skill{'s' if total != 1 else ''} identified, so "
            "this percentage is not reliable."
        )

    return {
        "job_title": job.job_title,
        "company": job.company,
        "skill_match_score": score,
        "ranking_score": ranking_score,
        "score_status": status,
        "confidence": confidence,
        "description_quality": job.description_quality,
        "description_source": job.description_source,
        "word_count": job.word_count,
        "matched_required_skills": direct,
        "partial_required_skills": related,
        "missing_required_skills": missing,
        "matched_preferred_skills": matched_preferred,
        "total_required_skills": total,
        "total_matched_required_skills": len(direct),
        "experience_level": job.experience_level,
        "missing_information": job.missing_information,
        "interpretation": interpretation,
        "warning": " ".join(warnings) or None,
    }
