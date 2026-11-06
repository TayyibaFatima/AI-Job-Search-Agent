"""
Run the search + ranking workflow from the terminal (no database needed).

    python -m backend.dev_scripts.run_search path/to/cv.pdf "ai engineer" London
    python -m backend.dev_scripts.run_search path/to/cv.pdf "ai engineer" "" gb   # whole country
    python -m backend.dev_scripts.run_search cv.pdf "python developer" "New York" us
"""

import sys

from backend.workflows.job_search_graph import build_job_search_graph


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    cv_path, keyword = sys.argv[1], sys.argv[2]
    location = sys.argv[3] if len(sys.argv) > 3 else ""
    country = sys.argv[4] if len(sys.argv) > 4 else "gb"

    result = build_job_search_graph().invoke({
        "cv_path": cv_path,
        "keyword": keyword,
        "location": location,
        "country": country,
        "results_per_page": 10,
    })

    if result.get("error"):
        print("\nERROR:", result["error"])
        sys.exit(1)

    print(f"\n{'#':<3} {'Score':<7} {'Conf.':<8} {'Skills':<8} Job")
    print("-" * 78)
    for job in result["ranked_jobs"]:
        score = job["skill_match_score"]
        shown = "n/a" if score is None else f"{score:.0f}%"
        print(
            f"{job['rank']:<3} {shown:<7} {job['confidence']:<8} "
            f"{job['total_matched_required_skills']}/"
            f"{job['total_required_skills']:<6} "
            f"{job['job_title']} — {job['company']}"
        )

    print("\nTop skill gaps:", ", ".join(
        gap["skill"] if isinstance(gap, dict) else str(gap)
        for gap in result.get("skill_gaps", [])[:8]
    ) or "none")


if __name__ == "__main__":
    main()
