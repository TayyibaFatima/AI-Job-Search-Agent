"""
Title relevance filter.

Job APIs search loosely: Remotive and Adzuna match the query words anywhere
in a listing, so "AI engineer" also returns "Service Desk Engineer" and an
office-assistant role whose text mentions AI once. This module keeps only
jobs whose TITLE fits what the user searched for.

How it works
------------
The query is split into
  * domain skills   ("ai", "python"...)   found with the skill taxonomy
  * other domain words ("marketing", "nurse"...)
  * role words      ("engineer", "developer"...)

A job is relevant when its title contains a domain skill (or a close
equivalent, e.g. "Machine Learning Engineer" for "AI engineer") or a domain
word. If the query is only a role word ("developer"), the title must
contain that role word. An empty query keeps everything.
"""

from __future__ import annotations

import re

from backend.tools.skill_taxonomy import find_skills, strip_skills

ROLE_WORDS = {
    "engineer", "developer", "scientist", "analyst", "specialist", "manager",
    "consultant", "programmer", "architect", "researcher", "designer",
    "administrator", "officer", "assistant", "executive", "associate",
    "technician", "coordinator", "writer", "tester", "advisor", "adviser",
}

IGNORED_WORDS = {
    # filler
    "a", "an", "and", "or", "the", "for", "in", "of", "at", "to", "with",
    "job", "jobs", "work", "position", "role", "roles", "opportunity",
    # seniority / contract type / place words never define the field
    "junior", "senior", "entry", "level", "graduate", "intern", "internship",
    "lead", "principal", "staff", "mid", "remote", "freelance", "contract",
    "full", "time", "part", "trainee", "apprentice", "placement",
}

# Skills that should count as a match for each other in a job TITLE.
EQUIVALENT_SKILLS = [
    {
        "ai", "machine learning", "deep learning", "generative ai",
        "large language models", "natural language processing",
        "computer vision", "neural networks", "reinforcement learning",
        "mlops", "rag", "prompt engineering", "data science",
    },
    {"python", "django", "flask", "fastapi"},
    {
        "javascript", "typescript", "react", "angular", "vue", "node.js",
        "next.js", "express",
    },
    {"data science", "data analysis", "machine learning", "statistics"},
    {"aws", "azure", "gcp"},
]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9+#]+", (text or "").lower())


def _stem(word: str) -> str:
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def parse_query(keyword: str) -> dict:
    skills = find_skills(keyword or "")
    leftovers = [_stem(w) for w in _words(strip_skills(keyword or ""))]

    roles = {w for w in leftovers if w in {_stem(r) for r in ROLE_WORDS}}
    others = {
        w for w in leftovers
        if w not in roles and w not in IGNORED_WORDS and len(w) > 1
    }

    return {"skills": skills, "others": others, "roles": roles}


def _skill_matches_title(skill: str, title_skills: set[str]) -> bool:
    if skill in title_skills:
        return True

    for group in EQUIVALENT_SKILLS:
        if skill in group and group & title_skills:
            return True

    return False


def is_relevant(title: str, keyword: str, query: dict | None = None) -> bool:
    query = query or parse_query(keyword)

    if not (query["skills"] or query["others"] or query["roles"]):
        return True  # nothing to judge against

    title_skills = set(find_skills(title))
    title_words = {_stem(w) for w in _words(title)}

    if query["skills"] or query["others"]:
        if any(_skill_matches_title(s, title_skills) for s in query["skills"]):
            return True
        return any(word in title_words for word in query["others"])

    return any(role in title_words for role in query["roles"])


def filter_relevant(jobs: list[dict], keyword: str) -> list[dict]:
    """Keep only jobs whose title fits the search keywords."""
    query = parse_query(keyword)
    kept = [j for j in jobs if is_relevant(j.get("title") or "", keyword, query)]

    dropped = len(jobs) - len(kept)
    if dropped:
        print(f"Relevance filter: dropped {dropped} of {len(jobs)} "
              f"jobs whose title does not match '{keyword}'.")

    return kept
