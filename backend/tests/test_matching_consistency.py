"""
Regression tests for the reported bugs:
  * the same job sometimes showed "Insufficient data" and sometimes 100%
  * 100% appeared when only 1-2 skills were extracted
"""

import pytest

from backend.models.candidate import CandidateProfile, Project
from backend.models.job import JobRequirements
from backend.tools import job_analyzer
from backend.tools.job_analyzer import analyze_job, ground_llm_skills
from backend.tools.job_filters import filter_jobs
from backend.tools.job_matcher import match_candidate_to_job
from backend.tools.job_ranking import rank_jobs
from backend.tools.skill_taxonomy import find_skills


@pytest.fixture
def candidate():
    return CandidateProfile(
        name="Test Candidate",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "scikit-learn"],
        projects=[
            Project(
                name="Booking bot",
                technologies=["n8n", "WhatsApp API"],
                description="Built REST APIs and LLM-powered automation.",
            )
        ],
    )


SNIPPET_JOB = {
    "title": "Junior AI Engineer",
    "company": "Acme",
    "description": (
        "Build machine learning models using Python and TensorFlow. "
        "You will deploy models with Docker and Kubernetes…"
    ),
}

FULL_JOB = {
    "title": "Junior AI Engineer",
    "company": "Acme",
    "description_source": "full_page",
    "description": """About the role
You will build and deploy machine learning models for our products.
Requirements:
- 2+ years of experience with Python and SQL
- Experience with PyTorch or TensorFlow
- Familiarity with Docker and REST APIs
- A degree in Computer Science
Nice to have:
- Kubernetes
- AWS experience
- Excellent communication skills
We offer a friendly, flexible workplace with great benefits for everyone
who joins the team, including flexible hours and a learning budget.""",
}


# ---------------------------------------------------------------- taxonomy
def test_token_boundaries():
    assert find_skills("Java developer") == ["java"]
    assert "java" not in find_skills("JavaScript and Node.js")
    assert "sql" not in find_skills("PostgreSQL and NoSQL")
    assert find_skills("Scikit learn, large language models, CI/CD") == [
        "scikit-learn", "large language models", "ci/cd",
    ]


def test_ambiguous_words_do_not_match():
    text = "Be able to react quickly, excel at teamwork. The rest of the team."
    assert find_skills(text) == []
    assert find_skills("Built React apps and Excel dashboards") == [
        "react", "excel",
    ]


# --------------------------------------------------------------- analyzer
def test_same_job_always_gives_same_analysis():
    first = analyze_job(SNIPPET_JOB)
    for _ in range(10):
        assert analyze_job(SNIPPET_JOB) == first


def test_preferred_section_headers_are_respected():
    result = analyze_job(FULL_JOB)
    assert {"python", "sql", "docker", "rest apis"} <= set(result.required_skills)
    assert set(result.preferred_skills) == {"kubernetes", "aws"}
    assert "kubernetes" not in result.required_skills


def test_llm_cannot_inject_ungrounded_or_soft_skills():
    text = "Junior AI Engineer\nWork with Python and Docker daily."
    grounded = ground_llm_skills(
        ["Python", "Kubernetes", "communication", "Machine Learning", "Docker"],
        text,
    )
    # Kubernetes / Machine Learning are not in the text; communication is soft.
    assert grounded == ["python", "docker"]


def test_llm_supplement_is_merged_when_grounded(monkeypatch):
    monkeypatch.setattr(
        job_analyzer,
        "llm_skills",
        lambda *a: {
            "required_skills": ["Terraform", "Snowflake"],  # only first in text
            "preferred_skills": [],
        },
    )
    job = {
        "title": "Platform Engineer",
        "company": "X",
        "description": "You will manage infrastructure with Terraform and Python.",
    }
    result = analyze_job(job)
    assert "terraform" in result.required_skills
    assert "snowflake" not in result.required_skills


def test_llm_failure_falls_back_to_deterministic(monkeypatch):
    monkeypatch.setattr(job_analyzer, "llm_skills", lambda *a: None)
    assert analyze_job(SNIPPET_JOB).required_skills


# ---------------------------------------------------------------- matching
def test_single_skill_is_never_a_confident_100(candidate):
    job = JobRequirements(
        job_title="Python Dev", required_skills=["python"],
        description_quality="limited",
    )
    report = match_candidate_to_job(candidate, job)
    assert report["skill_match_score"] == 100.0
    assert report["confidence"] == "low"
    assert report["score_status"] == "low_confidence"
    assert report["warning"]
    assert report["ranking_score"] < 80  # shrunk toward 50%


def test_no_skills_is_insufficient_not_a_fake_score(candidate):
    job = JobRequirements(job_title="Mystery Role", description_quality="insufficient")
    report = match_candidate_to_job(candidate, job)
    assert report["skill_match_score"] is None
    assert report["score_status"] == "insufficient_data"


def test_score_is_stable_across_runs(candidate):
    scores = {
        match_candidate_to_job(candidate, analyze_job(FULL_JOB))["skill_match_score"]
        for _ in range(10)
    }
    assert len(scores) == 1


def test_related_evidence_gets_partial_credit(candidate):
    job = JobRequirements(
        job_title="ML Engineer",
        required_skills=["machine learning", "python", "docker"],
        description_quality="good",
        description_source="full_page",
    )
    report = match_candidate_to_job(candidate, job)
    # ML is evidenced indirectly by scikit-learn -> related, not direct.
    assert report["partial_required_skills"] == ["machine learning"]
    assert report["skill_match_score"] == round((2 + 0.5) / 3 * 100, 1)


def test_ranking_prefers_well_evidenced_job_over_thin_100(candidate):
    thin = match_candidate_to_job(candidate, JobRequirements(
        job_title="Thin", required_skills=["python"]))            # 1/1
    solid = match_candidate_to_job(candidate, JobRequirements(
        job_title="Solid",
        required_skills=["python", "docker", "fastapi", "postgresql",
                         "git"],                                  # 4/5
        description_quality="good", description_source="full_page"))

    # Raw percentage alone would put the thin listing first (100 vs 80)...
    assert thin["skill_match_score"] > solid["skill_match_score"]

    # ...but the confidence-adjusted ranking must not.
    assert rank_jobs([thin, solid])[0]["job_title"] == "Solid"
    assert rank_jobs([solid, thin])[0]["job_title"] == "Solid"


# ----------------------------------------------------------------- filters
def test_exclusions_match_title_only():
    jobs = [
        {"title": "AI Engineer", "description": "You will lead to success"},
        {"title": "Lead AI Engineer", "description": "x"},
        {"title": "Data Scientist", "description": "Senior stakeholders"},
    ]
    kept = filter_jobs(jobs, excluded_keywords=["lead", "senior"])
    assert [j["title"] for j in kept] == ["AI Engineer", "Data Scientist"]


# ------------------------------------------------------- optional location
def test_empty_location_does_not_filter_or_break():
    jobs = [
        {"title": "AI Engineer", "location": "Manchester", "description": "x"},
        {"title": "Data Analyst", "location": "London", "description": "y"},
    ]
    assert len(filter_jobs(jobs, location="")) == 2
    assert len(filter_jobs(jobs, location=None)) == 2
    assert len(filter_jobs(jobs, location="London")) == 1


def test_search_omits_where_when_location_empty(monkeypatch):
    from backend.tools import job_search

    captured = {}

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"results": []}

    def fake_get(url, params=None, timeout=None):
        captured["url"], captured["params"] = url, params
        return FakeResponse()

    monkeypatch.setattr(job_search, "APP_ID", "id")
    monkeypatch.setattr(job_search, "APP_KEY", "key")
    monkeypatch.setattr(job_search.requests, "get", fake_get)

    job_search.search_jobs("python", "", country="us")
    assert "where" not in captured["params"]
    assert "/jobs/us/" in captured["url"]

    job_search.search_jobs("python", "Remote", country="gb")
    assert "where" not in captured["params"]

    job_search.search_jobs("python", "Leeds", country="gb")
    assert captured["params"]["where"] == "Leeds"
