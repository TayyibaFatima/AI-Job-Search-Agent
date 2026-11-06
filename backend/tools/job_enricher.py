"""
Fetch the full job description for a listing.

Adzuna's search API only returns a ~30-50 word preview of each listing.
That preview is the main reason matching was unreliable: too little text
to extract skills from. This module tries to retrieve the full text from
the listing page, using only *structured* sources so that navigation menus
and "similar jobs" widgets never leak extra skills into the analysis:

1. schema.org JobPosting JSON-LD (the most reliable source)
2. an element whose class/id marks it as the job description

If neither is found (or the site blocks us), the original preview is kept
and the job is clearly marked ``description_source = "snippet"`` so the
score is reported with lower confidence instead of pretending to be exact.
"""

from __future__ import annotations

import html
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

import requests

ENRICH_ENABLED = os.getenv("ENRICH_DESCRIPTIONS", "true").lower() != "false"
REQUEST_TIMEOUT = float(os.getenv("ENRICH_TIMEOUT_SECONDS", "8"))
MAX_WORKERS = int(os.getenv("ENRICH_MAX_WORKERS", "5"))
MAX_WORDS = 3000
MIN_USEFUL_WORDS = 40

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; JobSearchAgent/1.0; "
        "+personal-project)"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}

_JSON_LD = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_DESCRIPTION_HINT = re.compile(
    r"(job[-_ ]?description|jobdescription|adp-body|vacancy[-_ ]?description"
    r"|description[-_ ]?body|job[-_ ]?details?[-_ ]?content)",
    re.IGNORECASE,
)
_BLOCK_TAGS = {
    "p", "div", "li", "ul", "ol", "br", "tr", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6",
}
_SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "form"}
_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "wbr"}


def html_to_text(fragment: str) -> str:
    """Convert an HTML fragment to readable text with line breaks."""
    fragment = html.unescape(fragment or "")

    # JSON-LD descriptions are frequently HTML inside a string.
    fragment = re.sub(r"<\s*br\s*/?>", "\n", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"</\s*(p|div|li|h[1-6])\s*>", "\n", fragment,
                      flags=re.IGNORECASE)
    fragment = re.sub(r"<\s*li[^>]*>", "\n- ", fragment, flags=re.IGNORECASE)
    fragment = re.sub(r"<[^>]+>", " ", fragment)

    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip()
             for line in fragment.split("\n")]
    return "\n".join(line for line in lines if line)


def _find_job_posting(data) -> dict | None:
    """Locate a JobPosting object anywhere inside parsed JSON-LD."""
    if isinstance(data, list):
        for item in data:
            found = _find_job_posting(item)
            if found:
                return found
    elif isinstance(data, dict):
        node_type = data.get("@type")
        types = node_type if isinstance(node_type, list) else [node_type]
        if "JobPosting" in types:
            return data
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in data:
                found = _find_job_posting(data[key])
                if found:
                    return found
    return None


def extract_from_json_ld(page: str) -> str:
    for block in _JSON_LD.findall(page):
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, ValueError):
            continue

        posting = _find_job_posting(data)
        if not posting:
            continue

        parts = [
            posting.get("description"),
            posting.get("skills") if isinstance(posting.get("skills"), str)
            else " ".join(posting.get("skills") or [])
            if isinstance(posting.get("skills"), list) else "",
            posting.get("qualifications")
            if isinstance(posting.get("qualifications"), str) else "",
            posting.get("responsibilities")
            if isinstance(posting.get("responsibilities"), str) else "",
        ]
        text = html_to_text("\n".join(p for p in parts if p))
        if text:
            return text
    return ""


class _DescriptionContainerParser(HTMLParser):
    """Collect the text inside the first element that looks like a job description."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0            # nesting depth inside the container
        self.skip_depth = 0       # nesting depth inside skipped tags
        self.found = False
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        attr_text = " ".join(
            str(value) for key, value in attrs
            if key in ("class", "id", "itemprop") and value
        )

        if not self.found:
            if _DESCRIPTION_HINT.search(attr_text) or (
                dict(attrs).get("itemprop") == "description"
            ):
                self.found = True
                self.depth = 1
            return

        if tag in _VOID_TAGS:
            if tag == "br":
                self.chunks.append("\n")
            return

        self.depth += 1
        if tag in _SKIP_TAGS:
            self.skip_depth += 1
        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")
        if tag == "li":
            self.chunks.append("- ")

    def handle_endtag(self, tag):
        if not self.found or self.depth == 0 or tag in _VOID_TAGS:
            return

        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")
        if tag in _SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1

        self.depth -= 1
        if self.depth == 0:
            # Container closed: stop collecting.
            self.found = False
            self.done = True

    def handle_data(self, data):
        if self.found and self.depth > 0 and not self.skip_depth:
            self.chunks.append(data)

    done = False


def extract_from_container(page: str) -> str:
    parser = _DescriptionContainerParser()
    try:
        parser.feed(page)
    except Exception:
        return ""

    text = "".join(parser.chunks)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def fetch_full_description(url: str) -> str:
    """Return the full description text for a listing URL, or '' on failure."""
    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException:
        return ""

    if response.status_code != 200 or "html" not in response.headers.get(
        "Content-Type", "html"
    ):
        return ""

    page = response.text

    for extractor in (extract_from_json_ld, extract_from_container):
        text = extractor(page)

        if text and len(text.split()) >= MIN_USEFUL_WORDS:
            return _cap_words(text, MAX_WORDS)

    return ""


def _cap_words(text: str, limit: int) -> str:
    out, count = [], 0
    for line in text.split("\n"):
        n = len(line.split())
        if count + n > limit:
            break
        out.append(line)
        count += n
    return "\n".join(out)


def enrich_job(job: dict) -> dict:
    """
    Return a copy of ``job`` with the best available description.

    Adds:
      description_source: "full_page" | "snippet"
      snippet_description: the original Adzuna preview
    """
    enriched = dict(job)
    snippet = job.get("description") or ""
    enriched["snippet_description"] = snippet

    # Some sources (e.g. Remotive) already return the complete listing.
    if job.get("description_source") == "full_page":
        return enriched

    enriched["description_source"] = "snippet"

    if not ENRICH_ENABLED:
        return enriched

    full_text = fetch_full_description(job.get("redirect_url") or "")

    # Only accept the page text if it really adds information.
    if full_text and len(full_text.split()) > len(snippet.split()):
        enriched["description"] = full_text
        enriched["description_source"] = "full_page"

    return enriched


def enrich_jobs(jobs: list[dict]) -> list[dict]:
    """Enrich many jobs concurrently, preserving order."""
    if not jobs:
        return []

    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(jobs))) as pool:
        return list(pool.map(enrich_job, jobs))
