import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")


def normalize_text(value):
    """Normalize text for reliable duplicate comparison."""
    text = str(value or "").casefold()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9+#]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def description_quality(job):
    """Prefer listings with more useful description text."""
    description = str(job.get("description") or "").strip()
    return (
        len(description.split()),
        len(description),
        bool(job.get("redirect_url")),
    )


SUPPORTED_COUNTRIES = {
    "gb", "us", "au", "at", "br", "ca", "de", "es", "fr",
    "in", "it", "mx", "nl", "nz", "pl", "sg", "za",
}
DEFAULT_COUNTRY = os.getenv("ADZUNA_COUNTRY", "gb").lower()


def search_jobs(
    keyword,
    location,
    page=1,
    results_per_page=10,
    country=None,
):
    country = (country or DEFAULT_COUNTRY).lower()

    if country not in SUPPORTED_COUNTRIES:
        raise ValueError(
            f"Unsupported Adzuna country '{country}'. "
            f"Choose one of: {', '.join(sorted(SUPPORTED_COUNTRIES))}."
        )

    if not APP_ID or not APP_KEY:
        raise ValueError(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY are missing. Check your .env file."
        )

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "results_per_page": results_per_page,
        "what": keyword,
        **(
            {"where": location}
            if location and location.strip().lower()
            not in {"remote", "anywhere"}
            else {}
        ),
        "content-type": "application/json",
    }

    response = requests.get(url, params=params, timeout=20)

    if response.status_code != 200:
        raise Exception(
            f"Adzuna API error: {response.status_code}\n"
            f"{response.text}"
        )

    data = response.json()
    unique_jobs = {}
    duplicates_removed = 0

    for raw_job in data.get("results", []):
        title = raw_job.get("title") or "Unknown title"
        company = (
            raw_job.get("company", {}).get("display_name")
            or "Unknown company"
        )
        job_location = (
            raw_job.get("location", {}).get("display_name") or ""
        )

        job = {
            "title": title,
            "company": company,
            "location": job_location,
            "description": raw_job.get("description") or "",
            "salary_min": raw_job.get("salary_min"),
            "salary_max": raw_job.get("salary_max"),
            "contract_type": raw_job.get("contract_type"),
            "redirect_url": raw_job.get("redirect_url"),
        }

        # Primary duplicate key: normalized title and company.
        title_company_key = (
            normalize_text(title),
            normalize_text(company),
        )

        existing = unique_jobs.get(title_company_key)

        if existing is None:
            unique_jobs[title_company_key] = job
            continue

        duplicates_removed += 1

        # Keep the record with the most informative description.
        if description_quality(job) > description_quality(existing):
            unique_jobs[title_company_key] = job
            kept_location = job_location
        else:
            kept_location = existing["location"]

        print(
            f"Removed duplicate listing: {title} | {company}. "
            f"Kept the more informative record at: {kept_location}"
        )

    jobs = list(unique_jobs.values())

    print(
        f"Deduplication complete: removed {duplicates_removed} "
        f"duplicate title/company listings; "
        f"kept {len(jobs)} unique listings."
    )

    return jobs
