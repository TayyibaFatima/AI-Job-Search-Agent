import json

import pytest
import requests

from backend.tools import job_sources as js
from backend.tools.job_analyzer import analyze_job
from backend.tools.job_enricher import enrich_job

REMOTIVE_RAW = [
    {
        "title": "Python Backend Engineer", "company_name": "RemoteCo",
        "candidate_required_location": "Worldwide",
        "url": "https://remotive.com/remote-jobs/1", "job_type": "full_time",
        "salary": "$60k-$80k", "tags": ["python", "django", "docker"],
        "description": "<p>Build APIs with <b>Python</b>.</p><ul><li>SQL</li></ul>",
    },
    {
        "title": "AI Engineer", "company_name": "USCo",
        "candidate_required_location": "USA Only",
        "url": "https://remotive.com/remote-jobs/2", "tags": [],
        "description": "<p>Machine learning role.</p>",
    },
    {
        "title": "Data Analyst", "company_name": "AsiaCo",
        "candidate_required_location": "Asia, Pakistan",
        "url": "https://remotive.com/remote-jobs/3", "tags": [],
        "description": "<p>SQL and Excel.</p>",
    },
]


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(js, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(js, "_last_remotive_call", 0.0)


def fake_remotive(monkeypatch, calls):
    class Resp:
        status_code = 200
        def json(self):
            return {"jobs": REMOTIVE_RAW}

    def fake_get(url, **kw):
        calls.append(url)
        return Resp()

    monkeypatch.setattr(js.requests, "get", fake_get)


def test_remotive_normalises_and_marks_full_text(monkeypatch):
    fake_remotive(monkeypatch, [])
    jobs = js.search_remotive("python", "", 10)

    first = jobs[0]
    assert first["source_label"] == "Remotive"
    assert first["description_source"] == "full_page"
    assert "<p>" not in first["description"]
    assert "Tags: python, django, docker" in first["description"]
    assert first["redirect_url"].startswith("https://remotive.com/")

    analysed = analyze_job(first)
    assert {"python", "django", "docker", "sql"} <= set(analysed.required_skills)
    assert analysed.description_source == "full_page"


def test_remotive_location_is_an_eligibility_filter(monkeypatch):
    fake_remotive(monkeypatch, [])
    titles = lambda loc: {j["title"] for j in js.search_remotive("", loc, 10)}

    assert titles("") == {"Python Backend Engineer", "AI Engineer", "Data Analyst"}
    # Worldwide stays; region-specific kept only if it mentions Pakistan.
    assert titles("Pakistan") == {"Python Backend Engineer", "Data Analyst"}
    assert titles("Remote") == titles("")


def test_remotive_is_cached_so_api_is_not_hit_every_search(monkeypatch):
    calls = []
    fake_remotive(monkeypatch, calls)

    js.search_remotive("python", "", 10)
    js.search_remotive("python", "", 10)
    assert len(calls) == 1


def test_remotive_failure_falls_back_to_stale_cache(monkeypatch):
    calls = []
    fake_remotive(monkeypatch, calls)
    js.search_remotive("python", "", 10)

    # Expire the cache, then make the network fail.
    path = js._cache_path("python")
    data = json.loads(path.read_text())
    data["fetched_at"] = 0
    path.write_text(json.dumps(data))
    monkeypatch.setattr(js, "_last_remotive_call", 0.0)

    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(js.requests, "get", boom)
    stale = js.search_remotive("python", "", 10)
    assert [j["title"] for j in stale] == ["Python Backend Engineer"]


def test_enricher_skips_jobs_that_already_have_full_text(monkeypatch):
    def must_not_fetch(url):
        raise AssertionError("should not fetch")

    monkeypatch.setattr("backend.tools.job_enricher.fetch_full_description",
                        must_not_fetch)
    job = {"title": "T", "description": "full text", "description_source": "full_page",
           "redirect_url": "http://x"}
    assert enrich_job(job)["description_source"] == "full_page"


def test_jooble_requires_key(monkeypatch):
    monkeypatch.delenv("JOOBLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="JOOBLE_API_KEY"):
        js.search_jooble("python", "Karachi", "gb", 5)


def test_jooble_parses_results_and_never_leaks_key(monkeypatch):
    monkeypatch.setenv("JOOBLE_API_KEY", "SECRET-KEY-123")
    seen = {}

    class Resp:
        status_code = 200
        def json(self):
            return {"jobs": [{
                "title": "<b>Python</b> Developer", "company": "Acme",
                "location": "Karachi", "snippet": "Use <b>Python</b> and SQL&nbsp;daily",
                "salary": "PKR 300k", "type": "Full-time",
                "link": "https://jooble.org/jdp/1",
            }]}

    def fake_post(url, json=None, timeout=None):
        seen["url"], seen["body"] = url, json
        return Resp()

    monkeypatch.setattr(js.requests, "post", fake_post)
    jobs = js.search_jooble("python", "Karachi", "gb", 5)

    assert seen["body"]["location"] == "Karachi"
    assert jobs[0]["title"] == "Python Developer"
    assert "<b>" not in jobs[0]["description"]
    assert jobs[0]["source_label"] == "Jooble"

    # Empty location falls back to the selected country's name.
    js.search_jooble("python", "", "us", 5)
    assert seen["body"]["location"] == "United States"

    def explode(*a, **k):
        raise requests.ConnectionError("failed for https://jooble.org/api/SECRET-KEY-123")

    monkeypatch.setattr(js.requests, "post", explode)
    with pytest.raises(RuntimeError) as err:
        js.search_jooble("python", "x", "gb", 5)
    assert "SECRET-KEY-123" not in str(err.value)


def test_all_sources_skips_failures_and_dedupes(monkeypatch):
    shared = {"title": "Python Dev", "company": "Acme", "description": "short"}

    monkeypatch.setattr(js, "search_jobs", lambda **kw: [dict(shared)])
    monkeypatch.setattr(js, "search_jooble",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("no key")))
    monkeypatch.setattr(js, "search_remotive", lambda *a, **k: js._tag([
        {"title": "python dev", "company": "ACME",
         "description": "a much longer full description " * 5},
        {"title": "Other", "company": "Z", "description": "x"},
    ], "remotive"))

    jobs = js.search_jobs_from_source("all", "python", "", "gb", 10)
    assert len(jobs) == 2                      # Acme deduped across sources
    acme = next(j for j in jobs if "acme" in j["company"].lower())
    assert acme["source"] == "remotive"        # kept the longer description


def test_all_sources_fails_clearly_when_everything_fails(monkeypatch):
    boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
    monkeypatch.setattr(js, "search_jobs", boom)
    monkeypatch.setattr(js, "search_jooble", boom)
    monkeypatch.setattr(js, "search_remotive", boom)
    with pytest.raises(RuntimeError, match="No job source returned results"):
        js.search_jobs_from_source("all", "python")


def test_unknown_source_rejected():
    with pytest.raises(ValueError):
        js.search_jobs_from_source("monster", "python")
