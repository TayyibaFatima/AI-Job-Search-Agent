import os
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")


def search_jobs(
    keyword,
    location,
    page=1,
    results_per_page=10
):
    url = f"https://api.adzuna.com/v1/api/jobs/gb/search/{page}"

    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "results_per_page": results_per_page,
        "what": keyword,
        "where": location,
        "content-type": "application/json"
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        raise Exception(
            f"Adzuna API error: {response.status_code}\n"
            f"{response.text}"
        )

    data = response.json()

    jobs = []

    for job in data.get("results", []):
        jobs.append({
            "title": job.get("title"),
            "company": job.get("company", {}).get("display_name"),
            "location": job.get("location", {}).get("display_name"),
            "description": job.get("description"),
            "salary_min": job.get("salary_min"),
            "salary_max": job.get("salary_max"),
            "contract_type": job.get("contract_type"),
            "redirect_url": job.get("redirect_url")
        })

    return jobs