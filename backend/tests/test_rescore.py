"""Pasted descriptions and preview-vs-full-text ranking."""

from langgraph.checkpoint.memory import MemorySaver

from backend.models.candidate import CandidateProfile
from backend.models.job import JobRequirements
from backend.tools.job_matcher import match_candidate_to_job
from backend.tools.job_ranking import rank_jobs
from backend.tools.rescore import find_analyzed_job, rescore_job
from backend.workflows import job_search_graph as g
from backend.workflows import job_search_stage10_graph as s10

CANDIDATE = CandidateProfile(
    name="Test Candidate",
    skills=["Python", "FastAPI", "Docker", "PostgreSQL", "scikit-learn"],
)

JOBS = [
    {"title": "Python Developer", "company": "ThinCo", "location": "London",
     "description": "Python role.", "redirect_url": "http://x/1",
     "source_label": "Adzuna"},
    {"title": "Junior ML Engineer", "company": "RichCo", "location": "London",
     "description_source": "full_page", "redirect_url": "http://x/2",
     "description": (
         "Requirements:\n- Python\n- scikit-learn\n- Docker\n- SQL\n- REST APIs\n"
         "- Kubernetes\n- Spark\nYou will build machine learning services for "
         "our customers and work closely with the wider engineering team daily."
     )},
]

PASTED = (
    "About the role\nWe are hiring a Python Developer to build backend services.\n"
    "Requirements:\n- Python and FastAPI\n- PostgreSQL\n- Docker\n- Kubernetes\n"
    "- AWS\n- Terraform\nYou will work with a friendly team on APIs used by "
    "thousands of customers every day, with flexible hours and a learning budget."
)


def _patch(monkeypatch):
    monkeypatch.setattr(g, "extract_cv_text", lambda path: "cv")
    monkeypatch.setattr(g, "analyze_cv", lambda text: CANDIDATE)
    monkeypatch.setattr(g, "search_jobs_from_source", lambda **kw: [dict(j) for j in JOBS])
    monkeypatch.setattr(s10, "save_search_history", lambda **kw: None)


def test_full_text_job_outranks_preview_only_job():
    preview = match_candidate_to_job(CANDIDATE, JobRequirements(
        job_title="Preview", required_skills=["python", "docker", "fastapi"],
        description_quality="limited", description_source="snippet"))      # 3/3
    full = match_candidate_to_job(CANDIDATE, JobRequirements(
        job_title="Full", required_skills=["python", "docker", "kubernetes",
                                           "aws", "spark"],
        description_quality="good", description_source="full_page"))       # 2/5

    assert preview["skill_match_score"] > full["skill_match_score"]
    assert rank_jobs([preview, full])[0]["job_title"] == "Full"
    assert rank_jobs([full, preview])[0]["job_title"] == "Full"


def test_pasted_description_counts_as_full_text(monkeypatch):
    _patch(monkeypatch)
    state = g.build_job_search_graph().invoke({"cv_path": "x", "keyword": "python"})

    index = next(i for i, j in enumerate(state["ranked_jobs"])
                 if j["job_title"] == "Python Developer")
    before = state["ranked_jobs"][index]
    assert before["description_source"] == "snippet"
    assert "short preview" in (before["warning"] or "")

    updates = rescore_job(state, index, PASTED)
    after = next(j for j in updates["ranked_jobs"] if j["job_title"] == "Python Developer")

    assert after["description_source"] == "pasted"
    assert "short preview" not in (after["warning"] or "")
    assert after["confidence"] != "low"
    assert after["total_required_skills"] > before["total_required_skills"]
    assert after["redirect_url"] == "http://x/1"          # listing fields kept
    assert after["source_label"] == "Adzuna"
    assert len(updates["ranked_jobs"]) == len(state["ranked_jobs"])


def test_find_analyzed_job_rejects_bad_index(monkeypatch):
    _patch(monkeypatch)
    state = g.build_job_search_graph().invoke({"cv_path": "x", "keyword": "python"})
    try:
        find_analyzed_job(state, 99)
    except LookupError:
        return
    raise AssertionError("expected LookupError")


def test_rescore_can_be_saved_back_to_the_stored_run(monkeypatch):
    """The API stores the result with update_state; it must round-trip."""
    _patch(monkeypatch)
    graph = s10.build_stage10_graph(MemorySaver())
    config = {"configurable": {"thread_id": "t1"}}

    graph.invoke(
        {"cv_path": "x", "keyword": "python", "thread_id": "t1",
         "preferences": {}, "source": "all"},
        config,
    )
    state = graph.get_state(config).values
    index = next(i for i, j in enumerate(state["ranked_jobs"])
                 if j["job_title"] == "Python Developer")

    updates = rescore_job(state, index, PASTED)
    graph.update_state(config, updates, as_node="analyze_and_rank")

    saved = graph.get_state(config).values
    sources = {j["job_title"]: j["description_source"] for j in saved["ranked_jobs"]}
    assert sources["Python Developer"] == "pasted"

    # Materials lookups still resolve against the updated, re-ranked list.
    new_index = next(i for i, j in enumerate(saved["ranked_jobs"])
                     if j["job_title"] == "Python Developer")
    _, item = find_analyzed_job(saved, new_index)
    assert item["job"]["description_source"] == "pasted"
