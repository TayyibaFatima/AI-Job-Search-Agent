
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from backend.database import save_search_history
from backend.tools.job_filters import filter_jobs
from backend.workflows.job_search_graph import (
    JobSearchState,
    load_candidate_node,
    search_jobs_node,
    analyze_and_rank_node,
    generate_materials_node,
)


class Stage10State(JobSearchState, total=False):
    thread_id: str
    human_decision: str
    preferences: dict


def filter_jobs_node(state: Stage10State) -> dict:
    jobs = state.get("jobs", [])
    preferences = state.get("preferences", {})

    filtered_jobs = filter_jobs(
        jobs=jobs,
        location=preferences.get("location"),
        remote_only=preferences.get("remote_only", False),
        min_salary=preferences.get("min_salary"),
        excluded_keywords=preferences.get("excluded_keywords", []),
    )

    print(
        f"Job filtering completed: {len(filtered_jobs)} of "
        f"{len(jobs)} jobs matched your preferences."
    )

    return {"jobs": filtered_jobs}


def save_pending_history_node(state: Stage10State) -> dict:
    ranked_jobs = state.get("ranked_jobs", [])

    if not ranked_jobs:
        return {}

    save_search_history(
        candidate=state["candidate"],
        thread_id=state["thread_id"],
        keyword=state.get("keyword", "AI machine learning"),
        location=state.get("location", "London"),
        ranked_jobs=ranked_jobs,
        selected_job=ranked_jobs[0],
        application_materials=None,
        decision="pending",
    )

    print("Candidate and ranked jobs saved to PostgreSQL.")
    return {}


def review_job_node(state: Stage10State) -> dict:
    top_job = state["ranked_jobs"][0]

    decision = interrupt(
        {
            "message": "Review this job before generating application materials.",
            "job_title": top_job.get("job_title"),
            "company": top_job.get("company"),
            "skill_match_score": top_job.get("skill_match_score"),
            "match_tier": top_job.get("match_tier"),
            "score_status": top_job.get("score_status"),
            "missing_required_skills": top_job.get(
                "missing_required_skills", []
            ),
            "warning": top_job.get("warning"),
            "options": ["approve", "reject"],
        }
    )

    if isinstance(decision, str):
        decision = decision.strip().lower()

    return {"human_decision": decision}


def save_review_decision_node(state: Stage10State) -> dict:
    decision = state.get("human_decision")

    if decision not in ("approve", "reject"):
        raise ValueError("Decision must be 'approve' or 'reject'.")

    ranked_jobs = state.get("ranked_jobs", [])

    save_search_history(
        candidate=state["candidate"],
        thread_id=state["thread_id"],
        keyword=state.get("keyword", "AI machine learning"),
        location=state.get("location", "London"),
        ranked_jobs=ranked_jobs,
        selected_job=ranked_jobs[0] if ranked_jobs else None,
        application_materials=None,
        decision="approved" if decision == "approve" else "rejected",
    )

    print(f"Decision '{decision}' saved to PostgreSQL.")
    return {}


def route_after_review(state: Stage10State) -> str:
    if state.get("human_decision") == "approve":
        return "generate_materials"

    return "end"


def save_final_materials_node(state: Stage10State) -> dict:
    ranked_jobs = state.get("ranked_jobs", [])

    save_search_history(
        candidate=state["candidate"],
        thread_id=state["thread_id"],
        keyword=state.get("keyword", "AI machine learning"),
        location=state.get("location", "London"),
        ranked_jobs=ranked_jobs,
        selected_job=ranked_jobs[0] if ranked_jobs else None,
        application_materials=state.get("application_materials"),
        decision="approved",
    )

    print("Final application materials saved to PostgreSQL.")
    return {}


def build_stage10_graph(checkpointer):
    workflow = StateGraph(Stage10State)

    workflow.add_node("load_candidate", load_candidate_node)
    workflow.add_node("search_jobs", search_jobs_node)
    workflow.add_node("filter_jobs", filter_jobs_node)
    workflow.add_node("analyze_and_rank", analyze_and_rank_node)
    workflow.add_node("save_pending_history", save_pending_history_node)
    workflow.add_node("review_job", review_job_node)
    workflow.add_node("save_review_decision", save_review_decision_node)
    workflow.add_node("generate_materials", generate_materials_node)
    workflow.add_node("save_final_materials", save_final_materials_node)

    workflow.add_edge(START, "load_candidate")
    workflow.add_edge("load_candidate", "search_jobs")
    workflow.add_edge("search_jobs", "filter_jobs")
    workflow.add_edge("filter_jobs", "analyze_and_rank")

    workflow.add_conditional_edges(
        "analyze_and_rank",
        lambda state: "save_pending_history"
        if state.get("ranked_jobs")
        else "end",
        {
            "save_pending_history": "save_pending_history",
            "end": END,
        },
    )

    workflow.add_edge("save_pending_history", "review_job")
    workflow.add_edge("review_job", "save_review_decision")

    workflow.add_conditional_edges(
        "save_review_decision",
        route_after_review,
        {
            "generate_materials": "generate_materials",
            "end": END,
        },
    )

    workflow.add_edge("generate_materials", "save_final_materials")
    workflow.add_edge("save_final_materials", END)

    return workflow.compile(checkpointer=checkpointer)
