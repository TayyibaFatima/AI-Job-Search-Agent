"""
Multiple job sources behind one interface.

Every adapter returns jobs in the same shape the rest of the pipeline
already understands:

    title, company, location, description, salary_min, salary_max,
    contract_type, redirect_url
    + source, source_label           (where the job came from)
    + description_source             ("full_page" when the API already
                                      returns the complete text)

Sources
-------
adzuna   17 countries, needs ADZUNA_APP_ID / ADZUNA_APP_KEY
remotive remote jobs only, no key. Terms: credit Remotive and link back,
         listings are delayed ~24h, keep calls infrequent -> responses are
         cached and calls are spaced out.
jooble   60+ countries, needs a free JOOBLE_API_KEY (jooble.org/api/about)
all      every source that is available; failing ones are skipped
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import requests

from backend.tools.job_enricher import html_to_text
from backend.tools.job_relevance import filter_relevant, is_relevant, parse_query
from backend.tools.countries import COUNTRY_NAMES
from backend.tools.job_search import SUPPORTED_COUNTRIES, search_jobs

SOURCES = ("adzuna", "remotive", "jooble", "all")

SOURCE_LABELS = {
    "adzuna": "Adzuna",
    "remotive": "Remotive",
    "jooble": "Jooble",
}

CACHE_DIR = Path(os.getenv("SOURCE_CACHE_DIR", ".cache"))
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REMOTIVE_CACHE_HOURS = float(os.getenv("REMOTIVE_CACHE_HOURS", "6"))
REMOTIVE_MIN_INTERVAL_SECONDS = 30
REMOTIVE_FETCH_LIMIT = 100
REQUEST_TIMEOUT = 20


_WORLDWIDE_WORDS = ("worldwide", "anywhere", "global", "remote", "any location")
_last_remotive_call = 0.0


def _tag(jobs: list[dict], source: str) -> list[dict]:
    for job in jobs:
        job["source"] = source
        job["source_label"] = SOURCE_LABELS[source]
    return jobs


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


# --------------------------------------------------------------------------
# Remotive
# --------------------------------------------------------------------------

def _cache_path(keyword: str) -> Path:
    digest = hashlib.sha1(keyword.lower().encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"remotive_{digest}.json"


def _read_cached(path: Path) -> tuple[list | None, float]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload["jobs"], float(payload["fetched_at"])
    except (OSError, ValueError, KeyError):
        return None, 0.0


def _fetch_remotive(keyword: str) -> list[dict]:
    """Fetch (or reuse cached) raw Remotive listings for a keyword."""
    global _last_remotive_call

    path = _cache_path(keyword)
    cached, fetched_at = _read_cached(path)
    now = time.time()

    if cached is not None and now - fetched_at < REMOTIVE_CACHE_HOURS * 3600:
        print("Remotive: using cached results.")
        return cached

    if now - _last_remotive_call < REMOTIVE_MIN_INTERVAL_SECONDS:
        if cached is not None:
            print("Remotive: calls are rate limited, using cached results.")
            return cached
        raise RuntimeError(
            "Remotive asks for infrequent requests. Wait about 30 seconds "
            "and search again."
        )

    _last_remotive_call = now

    try:
        response = requests.get(
            REMOTIVE_URL,
            params={"search": keyword, "limit": REMOTIVE_FETCH_LIMIT},
            headers={"User-Agent": "JobSearchAgent/1.0 (personal project)"},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        raw_jobs = response.json().get("jobs", [])
    except (requests.RequestException, ValueError, RuntimeError) as error:
        if cached is not None:
            print(f"Remotive unavailable ({error}); using older cached results.")
            return cached
        raise RuntimeError(f"Remotive request failed: {error}") from error

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"fetched_at": now, "jobs": raw_jobs}),
            encoding="utf-8",
        )
    except OSError:
        pass

    return raw_jobs


def _remotive_eligible(region: str, wanted: str) -> bool:
    """
    The location box means "where can I work from" for a remote board.
    Keep worldwide listings always, and region-limited ones only if they
    mention what the user typed (e.g. "Pakistan", "Asia").
    """
    if not wanted:
        return True

    region_text = region.lower()
    if not region_text or any(w in region_text for w in _WORLDWIDE_WORDS):
        return True

    return wanted.lower() in region_text


def normalize_remotive(raw: dict) -> dict:
    region = (raw.get("candidate_required_location") or "").strip()

    description = html_to_text(raw.get("description") or "")
    tags = [str(tag) for tag in (raw.get("tags") or []) if tag]
    if tags:
        description += "\nTags: " + ", ".join(tags)

    return {
        "title": raw.get("title") or "Unknown title",
        "company": raw.get("company_name") or "Unknown company",
        "location": f"Remote - {region}" if region else "Remote",
        "description": description,
        "salary_min": None,
        "salary_max": None,
        "salary_text": raw.get("salary") or "",
        "contract_type": raw.get("job_type"),
        "redirect_url": raw.get("url"),
        # The API returns the full listing, so no page fetch is needed.
        "description_source": "full_page",
    }


def search_remotive(keyword: str, location: str, results_per_page: int) -> list[dict]:
    wanted = (location or "").strip()
    if wanted.lower() in {"remote", "anywhere", "worldwide"}:
        wanted = ""

    query = parse_query(keyword or "")
    jobs = []
    raw_jobs = _fetch_remotive((keyword or "").strip())

    for raw in raw_jobs:
        # Remotive's search matches words anywhere in the listing, so check
        # the title ourselves BEFORE counting towards the result limit.
        if not is_relevant(raw.get("title") or "", keyword, query):
            continue

        region = (raw.get("candidate_required_location") or "").strip()
        if _remotive_eligible(region, wanted):
            jobs.append(normalize_remotive(raw))
        if len(jobs) >= results_per_page:
            break

    print(f"Remotive: {len(jobs)} relevant of {len(raw_jobs)} returned.")

    return _tag(jobs, "remotive")


# --------------------------------------------------------------------------
# Jooble
# --------------------------------------------------------------------------

def normalize_jooble(raw: dict) -> dict:
    return {
        "title": html_to_text(raw.get("title") or "") or "Unknown title",
        "company": raw.get("company") or "Unknown company",
        "location": raw.get("location") or "",
        "description": html_to_text(raw.get("snippet") or ""),
        "salary_min": None,
        "salary_max": None,
        "salary_text": raw.get("salary") or "",
        "contract_type": raw.get("type") or None,
        "redirect_url": raw.get("link"),
    }


def search_jooble(
    keyword: str,
    location: str,
    country: str | None,
    results_per_page: int,
) -> list[dict]:
    api_key = os.getenv("JOOBLE_API_KEY")
    if not api_key:
        raise ValueError("Jooble is not set up. Add JOOBLE_API_KEY to your .env file.")

    place = (location or "").strip()
    if not place:
        place = COUNTRY_NAMES.get((country or "").lower(), "")

    try:
        # The key is part of the URL, so never log the URL or exception text.
        response = requests.post(
            f"https://jooble.org/api/{api_key}",
            json={"keywords": keyword, "location": place, "page": "1"},
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; JobSearchAgent/1.0)",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            f"Jooble request failed ({type(error).__name__})."
        ) from None

    if response.status_code in (401, 403):
        raise RuntimeError(
            "Jooble refused the request. Check JOOBLE_API_KEY in your .env file."
        )
    if response.status_code != 200:
        raise RuntimeError(f"Jooble is unavailable right now (HTTP {response.status_code}).")

    try:
        raw_jobs = response.json().get("jobs", [])
    except ValueError:
        raise RuntimeError("Jooble returned an unreadable response.") from None

    jobs = filter_relevant([normalize_jooble(raw) for raw in raw_jobs], keyword)
    return _tag(jobs[:results_per_page], "jooble")


# --------------------------------------------------------------------------
# Dispatcher
# --------------------------------------------------------------------------

def _dedupe(jobs: list[dict]) -> list[dict]:
    """Drop cross-source duplicates, keeping the listing with more text."""
    best: dict[tuple[str, str], dict] = {}
    order: list[tuple[str, str]] = []

    for job in jobs:
        key = (_norm(job.get("title")), _norm(job.get("company")))
        existing = best.get(key)

        if existing is None:
            best[key] = job
            order.append(key)
        elif len((job.get("description") or "").split()) > len(
            (existing.get("description") or "").split()
        ):
            best[key] = job

    return [best[key] for key in order]


def search_jobs_from_source(
    source: str,
    keyword: str,
    location: str = "",
    country: str | None = "gb",
    results_per_page: int = 10,
) -> list[dict]:
    source = (source or "adzuna").lower()

    if source not in SOURCES:
        raise ValueError(
            f"Unknown job source '{source}'. Choose one of: {', '.join(SOURCES)}."
        )

    if source == "adzuna":
        found = search_jobs(
            keyword=keyword,
            location=location,
            results_per_page=results_per_page,
            country=country,
        )
        return _tag(filter_relevant(found, keyword), "adzuna")

    if source == "remotive":
        return search_remotive(keyword, location, results_per_page)

    if source == "jooble":
        return search_jooble(keyword, location, country, results_per_page)

    # source == "all": use whatever works, skip what doesn't.
    collected: list[dict] = []
    problems: list[str] = []

    for name in ("adzuna", "jooble", "remotive"):
        try:
            found = search_jobs_from_source(
                name, keyword, location, country, results_per_page
            )
            print(f"Source {name}: {len(found)} jobs")
            collected.extend(found)
        except Exception as error:
            problems.append(f"{name}: {error}")
            print(f"Source {name} skipped: {error}")

    if not collected and problems:
        raise RuntimeError(
            "No job source returned results. " + " | ".join(problems)
        )

    return _dedupe(collected)


__all__ = [
    "SOURCES",
    "SUPPORTED_COUNTRIES",
    "search_jobs_from_source",
    "normalize_remotive",
    "normalize_jooble",
]
