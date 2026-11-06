from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.tools.job_sources import search_jobs_from_source
from backend.tools.job_enricher import enrich_jobs
from backend.tools.cv_parser import extract_cv_text
from backend.tools.cv_analyzer import analyze_cv
from backend.tools.job_analyzer import analyze_job
from backend.tools.job_matcher import (
    match_candidate_to_job,
    is_senior_role,
)
from backend.tools.job_ranking import (
    analyze_skill_gaps,
    rank_jobs,
)
from backend.tools.application_generator import (
    generate_application_materials,
)


class JobSearchState(TypedDict, total=False):
    cv_path: str
    keyword: str
    location: str
    country: str
    source: str
    results_per_page: int

    candidate: Any
    jobs: list
    analyzed_jobs: list
    match_reports: list
    ranked_jobs: list
    skill_gaps: list
    application_materials: Any
    error: str


def load_candidate_node(state: JobSearchState) -> dict:
    print("\n[1/4] Analyzing candidate CV...")

    cv_text = extract_cv_text(state["cv_path"])
    candidate = analyze_cv(cv_text)

    print("Candidate profile created.")

    return {"candidate": candidate}


def search_jobs_node(state: JobSearchState) -> dict:
    print("\n[2/4] Searching live jobs...")

    keyword = state.get("keyword", "AI machine learning")
    location = state.get("location") or ""
    results_per_page = state.get("results_per_page", 5)

    print(f"Search keyword: {keyword!r}")
    print(f"Search location: {location!r}")
    print(f"Results requested: {results_per_page}")

    jobs = search_jobs_from_source(
        source=state.get("source") or "adzuna",
        keyword=keyword,
        location=location,
        country=state.get("country"),
        results_per_page=results_per_page,
    )

    print(f"Retrieved {len(jobs)} jobs.")

    for index, job in enumerate(jobs, start=1):
        description = job.get("description") or ""

        print(
            f"  {index}. {job.get('title', 'Unknown title')} "
            f"— {job.get('company', 'Unknown company')}"
        )
        print(
            f"     Description length: "
            f"{len(description.split())} words"
        )

    return {"jobs": jobs}


def analyze_and_rank_node(state: JobSearchState) -> dict:
    print("\n[3/4] Analyzing and ranking jobs...")

    candidate = state["candidate"]
    jobs = state.get("jobs", [])

    eligible_jobs = []
    filtered_jobs = []

    for job in jobs:
        title = job.get("title") or ""

        if is_senior_role(title):
            filtered_jobs.append(job)
            print(f"Filtered senior role: {title}")
        else:
            eligible_jobs.append(job)

    # Adzuna returns only a short preview. Try to fetch the full listing
    # text so skills are extracted from real requirements, not a teaser.
    eligible_jobs = enrich_jobs(eligible_jobs)

    full_pages = sum(
        1 for job in eligible_jobs
        if job.get("description_source") == "full_page"
    )
    print(
        f"Retrieved {len(jobs)} jobs | senior filtered: "
        f"{len(filtered_jobs)} | eligible: {len(eligible_jobs)} | "
        f"full listing text found for {full_pages}"
    )

    analyzed_jobs = []
    match_reports = []
    skipped_jobs = []

    for index, job in enumerate(eligible_jobs, start=1):
        title = job.get("title") or "Unknown title"
        company = job.get("company") or "Unknown company"

        try:
            requirements = analyze_job(job)
            report = match_candidate_to_job(candidate, requirements)

            report["redirect_url"] = job.get("redirect_url")
            report["location"] = job.get("location")
            report["salary_min"] = job.get("salary_min")
            report["salary_max"] = job.get("salary_max")
            report["contract_type"] = job.get("contract_type")
            report["source"] = job.get("source")
            report["source_label"] = job.get("source_label")
            report["salary_text"] = job.get("salary_text")

            analyzed_jobs.append({
                "job": job,
                "requirements": requirements,
                "report": report,
            })
            match_reports.append(report)

            print(
                f"  {index}/{len(eligible_jobs)} {title} — {company} | "
                f"source={requirements.description_source} "
                f"words={requirements.word_count} "
                f"skills={len(requirements.required_skills)} "
                f"score={report['skill_match_score']} "
                f"confidence={report['confidence']}"
            )

        except Exception as error:
            skipped_jobs.append({
                "title": title,
                "company": company,
                "error": f"{type(error).__name__}: {error}",
            })
            print(f"  Skipping '{title}' — {company}: {error}")

    print(
        f"Analyzed: {len(match_reports)} | skipped: {len(skipped_jobs)}"
    )

    if not match_reports:
        return {
            "analyzed_jobs": [],
            "match_reports": [],
            "ranked_jobs": [],
            "skill_gaps": [],
            "error": (
                "No jobs could be analyzed. Review the terminal "
                "logs for API, network, or job-analysis errors."
            ),
        }

    ranked_jobs = rank_jobs(match_reports)
    skill_gaps = analyze_skill_gaps(match_reports)

    return {
        "analyzed_jobs": analyzed_jobs,
        "match_reports": match_reports,
        "ranked_jobs": ranked_jobs,
        "skill_gaps": skill_gaps,
        "error": "",
    }


def route_after_ranking(state: JobSearchState) -> str:
    if state.get("ranked_jobs"):
        return "generate_materials"

    return "end"


def generate_materials_node(state: JobSearchState) -> dict:
    print("\n[4/4] Generating application materials...")

    ranked_jobs = state.get("ranked_jobs", [])

    if not ranked_jobs:
        return {
            "error": "No ranked jobs are available for application materials."
        }

    top_job = ranked_jobs[0]

    selected = next(
        (
            item
            for item in state.get("analyzed_jobs", [])
            if (
                item["report"].get("job_title")
                == top_job.get("job_title")
                and item["report"].get("company")
                == top_job.get("company")
            )
        ),
        None,
    )

    if selected is None:
        return {
            "error": (
                "Could not find the original requirements "
                "for the highest-ranked job."
            )
        }

    try:
        materials = generate_application_materials(
            candidate=state["candidate"],
            job=selected["requirements"],
            match_report=selected["report"],
        )

        print("Application materials generated.")

        return {
            "application_materials": materials,
            "error": "",
        }

    except Exception as error:
        print(
            f"Application-material generation failed: "
            f"{type(error).__name__}: {error}"
        )

        return {
            "error": (
                "Jobs were analyzed and ranked, but application "
                "materials could not be generated."
            )
        }


def build_job_search_graph():
    workflow = StateGraph(JobSearchState)

    workflow.add_node("load_candidate", load_candidate_node)
    workflow.add_node("search_jobs", search_jobs_node)
    workflow.add_node("analyze_and_rank", analyze_and_rank_node)
    workflow.add_node("generate_materials", generate_materials_node)

    workflow.add_edge(START, "load_candidate")
    workflow.add_edge("load_candidate", "search_jobs")
    workflow.add_edge("search_jobs", "analyze_and_rank")

    workflow.add_conditional_edges(
        "analyze_and_rank",
        route_after_ranking,
        {
            "generate_materials": "generate_materials",
            "end": END,
        },
    )

    workflow.add_edge("generate_materials", END)

    return workflow.compile()


job_search_graph = build_job_search_graph()
