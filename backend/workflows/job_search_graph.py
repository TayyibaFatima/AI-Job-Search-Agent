
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.tools.job_search import search_jobs
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

    jobs = search_jobs(
        keyword=state.get("keyword", "AI machine learning"),
        location=state.get("location", "London"),
        results_per_page=state.get("results_per_page", 5),
    )

    print(f"Retrieved {len(jobs)} jobs.")

    return {"jobs": jobs}


def analyze_and_rank_node(state: JobSearchState) -> dict:
    print("\n[3/4] Analyzing and ranking jobs...")

    candidate = state["candidate"]

    eligible_jobs = [
        job for job in state["jobs"]
        if not is_senior_role(job.get("title") or "")
    ]

    print(f"{len(eligible_jobs)} jobs passed the senior-title filter.")

    analyzed_jobs = []
    match_reports = []

    for index, job in enumerate(eligible_jobs, start=1):
        print(
            f"\nAnalyzing job {index}/{len(eligible_jobs)}: "
            f"{job.get('title')} — {job.get('company')}"
        )

        try:
            requirements = analyze_job(job)

            report = match_candidate_to_job(
                candidate,
                requirements,
            )

            analyzed_jobs.append({
                "job": job,
                "requirements": requirements,
                "report": report,
            })

            match_reports.append(report)

            print("Analysis completed.")

        except Exception as error:
            print(
                f"Skipping job '{job.get('title', 'Unknown')}': "
                f"{error}"
            )

    if not match_reports:
        return {
            "analyzed_jobs": [],
            "match_reports": [],
            "ranked_jobs": [],
            "skill_gaps": [],
            "error": (
                "No jobs could be analyzed. Check the API quota, "
                "network connection, and job descriptions."
            ),
        }

    ranked_jobs = rank_jobs(match_reports)
    skill_gaps = analyze_skill_gaps(match_reports)

    print(f"\nSuccessfully analyzed {len(match_reports)} jobs.")
    print("Ranking completed.")

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

    top_job = state["ranked_jobs"][0]

    selected = next(
        (
            item for item in state["analyzed_jobs"]
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
