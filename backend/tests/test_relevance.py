"""
Regression: searching "AI engineer" returned Office Assistant, Freelance
Writer, Service Desk Engineer and Inside Sales jobs.
"""

import pytest

from backend.tools import job_sources as js
from backend.tools.job_analyzer import ground_llm_skills
from backend.tools.job_matcher import expand_skill
from backend.tools.job_relevance import filter_relevant, is_relevant

JUNK = [
    "Remote Office Assistant",
    "Freelance Writer",
    "Tier III Service Desk Engineer",
    "Inside Sales Contractor",
]
GOOD = [
    "Cyber AI Engineer - Remote",
    "AI Engineer - Remote Europe",
    "Machine Learning Engineer",
    "Generative AI Developer",
    "Senior LLM Engineer",
    "Data Scientist",
]


@pytest.mark.parametrize("title", JUNK)
def test_unrelated_titles_rejected_for_ai_engineer(title):
    assert not is_relevant(title, "AI engineer")


@pytest.mark.parametrize("title", GOOD)
def test_related_titles_kept_for_ai_engineer(title):
    assert is_relevant(title, "AI engineer")


def test_role_only_query_requires_the_role_word():
    assert is_relevant("Python Developer", "developer")
    assert not is_relevant("Office Assistant", "developer")


def test_equivalent_skills_and_plain_words():
    assert is_relevant("Django Developer", "python developer")
    assert not is_relevant("Java Developer", "python developer")
    assert is_relevant("Marketing Manager", "marketing manager")
    assert not is_relevant("Sales Manager", "marketing manager")


def test_empty_query_keeps_everything():
    jobs = [{"title": "Anything"}, {"title": "Else"}]
    assert filter_relevant(jobs, "") == jobs


def test_remotive_relevance_applies_before_result_limit(monkeypatch, tmp_path):
    """Junk listed first must not use up the result limit."""
    raw = [
        {"title": t, "company_name": "C", "candidate_required_location": "Worldwide",
         "url": "u", "tags": [], "description": "<p>text</p>"}
        for t in JUNK + ["AI Engineer", "Machine Learning Engineer"]
    ]

    class Resp:
        status_code = 200
        def json(self):
            return {"jobs": raw}

    monkeypatch.setattr(js, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(js, "_last_remotive_call", 0.0)
    monkeypatch.setattr(js.requests, "get", lambda *a, **k: Resp())

    jobs = js.search_remotive("AI engineer", "", 2)
    assert [j["title"] for j in jobs] == ["AI Engineer", "Machine Learning Engineer"]


def test_adzuna_and_jooble_results_are_also_filtered(monkeypatch):
    mixed = [{"title": t, "company": "X", "description": ""} for t in JUNK + GOOD[:2]]
    monkeypatch.setattr(js, "search_jobs", lambda **kw: [dict(j) for j in mixed])

    jobs = js.search_jobs_from_source("adzuna", "AI engineer", "", "gb", 10)
    assert {j["title"] for j in jobs} == set(GOOD[:2])


# ---- smaller bugs found in the same results screen
def test_ci_cd_is_not_split_into_ci_and_cd():
    assert expand_skill("ci/cd") == ["ci/cd"]
    assert expand_skill("AI & Machine Learning") == ["AI", "Machine Learning"]


def test_llm_cannot_return_plain_english_words_as_skills():
    text = "Write articles. The rest of the team will help. You will excel at teamwork."
    assert ground_llm_skills(["REST", "rest", "Excel"], text) == []
