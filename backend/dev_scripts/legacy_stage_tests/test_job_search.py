from backend.tools.job_search import search_jobs


jobs = search_jobs(
    keyword="AI machine learning",
    location="London"
)

print(f"\nFound {len(jobs)} jobs\n")

for job in jobs:
    print("=" * 60)
    print("Title:", job["title"])
    print("Company:", job["company"])
    print("Location:", job["location"])
    print("Salary:", job["salary_min"], "-", job["salary_max"])
    print("URL:", job["redirect_url"])