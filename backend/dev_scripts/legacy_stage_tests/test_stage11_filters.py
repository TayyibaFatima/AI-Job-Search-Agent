
from backend.tools.job_filters import filter_jobs


def main():
    sample_jobs = [
        {
            "title": "Junior AI Engineer",
            "company": "Alpha AI",
            "location": "London",
            "description": "Remote Python and machine learning role.",
            "salary_min": 35000,
            "salary_max": 45000,
        },
        {
            "title": "Senior Data Scientist",
            "company": "Beta Analytics",
            "location": "London",
            "description": "Remote role involving Python and analytics.",
            "salary_min": 50000,
            "salary_max": 65000,
        },
        {
            "title": "Junior Python Developer",
            "company": "Gamma Tech",
            "location": "Manchester",
            "description": "Office-based Python development.",
            "salary_min": 30000,
            "salary_max": 38000,
        },
        {
            "title": "AI Intern",
            "company": "Delta Labs",
            "location": "London",
            "description": "Remote internship using Python.",
            "salary_min": None,
            "salary_max": None,
        },
    ]

    print("TEST 1: Location filter")
    results = filter_jobs(sample_jobs, location="London")
    assert len(results) == 3
    print("Passed.")

    print("\nTEST 2: Remote-only filter")
    results = filter_jobs(sample_jobs, remote_only=True)
    assert len(results) == 3
    print("Passed.")

    print("\nTEST 3: Minimum salary filter")
    results = filter_jobs(sample_jobs, min_salary=40000)
    assert len(results) == 2
    print("Passed.")

    print("\nTEST 4: Excluded keywords")
    results = filter_jobs(
        sample_jobs,
        excluded_keywords=["senior", "intern"],
    )
    assert len(results) == 2
    print("Passed.")

    print("\nTEST 5: Combined filters")
    results = filter_jobs(
        sample_jobs,
        location="London",
        remote_only=True,
        min_salary=40000,
        excluded_keywords=["senior"],
    )
    assert len(results) == 1
    assert results[0]["company"] == "Alpha AI"
    print("Passed.")

    print("\nAll Stage 11 filter tests passed.")


if __name__ == "__main__":
    main()
