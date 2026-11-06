"""End-to-end run of the search workflow with external services mocked."""

from backend.models.candidate import CandidateProfile
from backend.workflows import job_search_graph as g

CANDIDATE = CandidateProfile(
    name="Test Candidate",
    skills=["Python", "FastAPI", "Docker", "PostgreSQL", "scikit-learn"],
)

JOBS = [
    {   # thin preview: only 1 skill findable
        "title": "Python Developer", "company": "ThinCo", "location": "London",
        "description": "Python role.", "redirect_url": "http://x/1",
    },
    {   # richer text
        "title": "Junior ML Engineer", "company": "RichCo", "location": "London",
        "description_source": "full_page", "redirect_url": "http://x/2",
        "description": (
            "Requirements:\n- Python\n- scikit-learn\n- Docker\n- SQL\n"
            "- REST APIs\nYou will build machine learning services for our "
            "customers and work closely with the wider engineering team daily."
        ),
    },
    {   # nothing extractable
        "title": "Graduate Opportunity", "company": "VagueCo",
        "location": "London", "description": "",
        "redirect_url": "http://x/3",
    },
    {"title": "Senior Python Engineer", "company": "BigCo",
     "location": "London", "description": "Python", "redirect_url": "http://x/4"},
]


def _run(monkeypatch):
    monkeypatch.setattr(g, "extract_cv_text", lambda path: "cv text")
    monkeypatch.setattr(g, "analyze_cv", lambda text: CANDIDATE)
    monkeypatch.setattr(g, "search_jobs_from_source", lambda **kw: [dict(j) for j in JOBS])
    monkeypatch.setattr(g, "generate_application_materials",
                        lambda **kw: {"tailored_summary": "ok"})
    return g.build_job_search_graph().invoke(
        {"cv_path": "x.pdf", "keyword": "python", "location": ""}
    )


def test_workflow_ranks_and_labels_every_job(monkeypatch):
    result = _run(monkeypatch)
    ranked = result["ranked_jobs"]

    titles = [j["job_title"] for j in ranked]
    assert "Senior Python Engineer" not in titles          # senior filtered
    assert titles[0] == "Junior ML Engineer"               # evidenced job first

    by_title = {j["job_title"]: j for j in ranked}
    assert by_title["Python Developer"]["score_status"] == "low_confidence"
    assert by_title["Graduate Opportunity"]["score_status"] == "insufficient_data"
    assert by_title["Junior ML Engineer"]["skill_match_score"] is not None
    assert ranked[-1]["job_title"] == "Graduate Opportunity"  # unscored last


def test_workflow_is_repeatable(monkeypatch):
    first = [(j["job_title"], j["skill_match_score"], j["score_status"])
             for j in _run(monkeypatch)["ranked_jobs"]]
    for _ in range(5):
        again = [(j["job_title"], j["skill_match_score"], j["score_status"])
                 for j in _run(monkeypatch)["ranked_jobs"]]
        assert again == first
