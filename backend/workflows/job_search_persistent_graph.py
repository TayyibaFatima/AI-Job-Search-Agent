
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from backend.workflows.job_search_graph import (
    JobSearchState,
    load_candidate_node,
    search_jobs_node,
    analyze_and_rank_node,
    generate_materials_node,
)


class PersistentJobSearchState(JobSearchState, total=False):
    human_decision: str


def review_job_node(state: PersistentJobSearchState) -> dict:
    top_job = state["ranked_jobs"][0]

    decision = interrupt({
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
    })

    if isinstance(decision, str):
        decision = decision.strip().lower()

    return {"human_decision": decision}


def route_after_review(state: PersistentJobSearchState) -> str:
    if state.get("human_decision") == "approve":
        return "generate_materials"

    return "end"


def build_persistent_job_search_graph(checkpointer):
    workflow = StateGraph(PersistentJobSearchState)

    workflow.add_node("load_candidate", load_candidate_node)
    workflow.add_node("search_jobs", search_jobs_node)
    workflow.add_node("analyze_and_rank", analyze_and_rank_node)
    workflow.add_node("review_job", review_job_node)
    workflow.add_node("generate_materials", generate_materials_node)

    workflow.add_edge(START, "load_candidate")
    workflow.add_edge("load_candidate", "search_jobs")
    workflow.add_edge("search_jobs", "analyze_and_rank")

    workflow.add_conditional_edges(
        "analyze_and_rank",
        lambda state: (
            "review_job" if state.get("ranked_jobs") else "end"
        ),
        {
            "review_job": "review_job",
            "end": END,
        },
    )

    workflow.add_conditional_edges(
        "review_job",
        route_after_review,
        {
            "generate_materials": "generate_materials",
            "end": END,
        },
    )

    workflow.add_edge("generate_materials", END)

    return workflow.compile(checkpointer=checkpointer)
