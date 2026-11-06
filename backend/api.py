
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from backend.database import (
    get_database_url,
    get_recent_search_history,
    save_search_history,
    setup_application_tables,
)
from backend.tools.application_generator import generate_application_materials
from backend.tools.countries import COUNTRY_NAMES, location_label
from backend.tools.job_search import SUPPORTED_COUNTRIES
from backend.tools.job_sources import SOURCES
from backend.workflows.job_search_stage10_graph import build_stage10_graph


load_dotenv()

UPLOAD_DIR = Path("uploads")
MAX_CV_SIZE = 10 * 1024 * 1024


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")


class MaterialsRequest(BaseModel):
    # Position of the chosen job in the ranked list (0 = top match).
    job_index: int = Field(ge=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_application_tables()

    with PostgresSaver.from_conn_string(
        get_database_url()
    ) as checkpointer:
        checkpointer.setup()
        app.state.graph = build_stage10_graph(checkpointer)
        yield


app = FastAPI(
    title="AI Job Search and Application Agent",
    description=(
        "Search and rank jobs, review a selected job, "
        "and generate tailored application materials."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "AI Job Search and Application Agent API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/api/search")
def start_search(
    request: Request,
    cv_file: UploadFile = File(...),
    keyword: str = Form("AI machine learning"),
    location: str = Form(""),
    country: str = Form("gb"),
    source: str = Form("all"),
    results_per_page: int = Form(10, ge=1, le=20),
    remote_only: bool = Form(False),
    min_salary: float | None = Form(None, gt=0),
    excluded_keywords: str = Form("senior,lead,principal"),
):
    if not cv_file.filename or Path(cv_file.filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Upload your CV as a PDF file.",
        )

    source = source.strip().lower()
    if source not in SOURCES:
        raise HTTPException(
            status_code=400,
            detail="Unknown job source. Choose one of: " + ", ".join(SOURCES),
        )

    country = country.strip().lower()

    if source == "adzuna" and country not in SUPPORTED_COUNTRIES:
        place = COUNTRY_NAMES.get(country)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Adzuna doesn't cover {place}." if place
                else "Adzuna can't search worldwide."
            ),
        )

    contents = cv_file.file.read()

    if len(contents) > MAX_CV_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The CV must be 10 MB or smaller.",
        )

    if not contents.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="The uploaded file does not appear to be a valid PDF.",
        )

    thread_id = f"stage12-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    excluded = [
        item.strip()
        for item in excluded_keywords.split(",")
        if item.strip()
    ]

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    cv_path = UPLOAD_DIR / f"{thread_id}.pdf"
    cv_path.write_bytes(contents)

    try:
        result = request.app.state.graph.invoke(
            {
                "thread_id": thread_id,
                "cv_path": str(cv_path.resolve()),
                "keyword": keyword.strip(),
                "location": location.strip(),
                "country": country.strip().lower(),
                "source": source,
                "results_per_page": results_per_page,
                "preferences": {
                    # Only Adzuna's location is a place name we can match
                    # on; other sources apply the location themselves.
                    "location": location.strip() if source == "adzuna" else "",
                    "remote_only": remote_only,
                    "min_salary": min_salary,
                    "excluded_keywords": excluded,
                },
            },
            config=config,
        )
    except (ValueError, RuntimeError) as error:
        # Source problems (missing key, rejected request, ...) have short,
        # safe messages that are useful to show directly.
        print(f"Search workflow failed: {error}")
        raise HTTPException(status_code=502, detail=str(error)[:200]) from error
    except Exception as error:
        print(f"Search workflow failed: {error}")
        raise HTTPException(
            status_code=500,
            detail="The job-search workflow failed. Check the server terminal.",
        ) from error
    finally:
        cv_path.unlink(missing_ok=True)
        cv_file.file.close()

    ranked_jobs = result.get("ranked_jobs", [])

    return jsonable_encoder(
        {
            "thread_id": thread_id,
            "status": "awaiting_review" if ranked_jobs else "no_jobs",
            "ranked_jobs": ranked_jobs,
            "top_job": ranked_jobs[0] if ranked_jobs else None,
            "error": result.get("error") or None,
            "message": (
                "Review the ranked jobs and approve or reject the top job."
                if ranked_jobs
                else "No suitable jobs were found. Try changing your search."
            ),
        }
    )


@app.post("/api/runs/{thread_id}/decision")
def review_search(
    thread_id: str,
    body: ReviewRequest,
    request: Request,
):
    config = {"configurable": {"thread_id": thread_id}}

    try:
        snapshot = request.app.state.graph.get_state(config)
        state = snapshot.values

        if not state:
            raise HTTPException(
                status_code=404,
                detail="Search run not found.",
            )

        if not state.get("ranked_jobs"):
            raise HTTPException(
                status_code=409,
                detail="This search has no ranked jobs to review.",
            )

        if state.get("human_decision") in ("approve", "reject"):
            raise HTTPException(
                status_code=409,
                detail="A review decision has already been recorded.",
            )

        result = request.app.state.graph.invoke(
            Command(resume=body.decision),
            config=config,
        )

    except HTTPException:
        raise
    except Exception as error:
        print(f"Review workflow failed: {error}")
        raise HTTPException(
            status_code=500,
            detail="The review failed. Check the server terminal.",
        ) from error

    materials = result.get("application_materials")

    return jsonable_encoder(
        {
            "thread_id": thread_id,
            "decision": body.decision,
            "status": (
                "completed"
                if body.decision == "approve" and materials
                else "rejected"
                if body.decision == "reject"
                else "generation_failed"
            ),
            "application_materials": materials,
            "error": result.get("error") or None,
        }
    )


@app.post("/api/runs/{thread_id}/materials")
def generate_materials_for_job(
    thread_id: str,
    body: MaterialsRequest,
    request: Request,
):
    """Generate application materials for any job from a finished search."""
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = request.app.state.graph.get_state(config).values
    except Exception as error:
        print(f"Could not load search run: {error}")
        raise HTTPException(
            status_code=500,
            detail="Could not load this search run. Check the server terminal.",
        ) from error

    if not state:
        raise HTTPException(status_code=404, detail="Search run not found.")

    ranked_jobs = state.get("ranked_jobs", [])
    if body.job_index >= len(ranked_jobs):
        raise HTTPException(status_code=400, detail="That job is not in this search.")

    job = ranked_jobs[body.job_index]

    # If two listings share a title and company, pick the matching occurrence.
    occurrence = sum(
        1
        for earlier in ranked_jobs[: body.job_index]
        if earlier.get("job_title") == job.get("job_title")
        and earlier.get("company") == job.get("company")
    )
    candidates = [
        item
        for item in state.get("analyzed_jobs", [])
        if item["report"].get("job_title") == job.get("job_title")
        and item["report"].get("company") == job.get("company")
    ]
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="Could not find the original requirements for this job.",
        )
    selected = candidates[min(occurrence, len(candidates) - 1)]

    try:
        materials = generate_application_materials(
            candidate=state["candidate"],
            job=selected["requirements"],
            match_report=selected["report"],
        )
    except Exception as error:
        print(f"Materials generation failed: {error}")
        raise HTTPException(
            status_code=500,
            detail="Could not generate application materials. Check the server terminal.",
        ) from error

    try:
        save_search_history(
            candidate=state["candidate"],
            thread_id=thread_id,
            keyword=state.get("keyword", ""),
            location=location_label(state.get("location"), state.get("country")),
            ranked_jobs=ranked_jobs,
            selected_job=job,
            application_materials=materials,
            decision="approved",
        )
    except Exception as error:
        # The drafts are still returned; only the history record failed.
        print(f"Could not save materials to history: {error}")

    return jsonable_encoder(
        {
            "thread_id": thread_id,
            "job_index": body.job_index,
            "job": job,
            "application_materials": materials,
        }
    )


@app.get("/api/runs/{thread_id}")
def get_search_run(thread_id: str, request: Request):
    config = {"configurable": {"thread_id": thread_id}}

    snapshot = request.app.state.graph.get_state(config)
    state = snapshot.values

    if not state:
        raise HTTPException(
            status_code=404,
            detail="Search run not found.",
        )

    decision = state.get("human_decision")
    ranked_jobs = state.get("ranked_jobs", [])
    materials = state.get("application_materials")

    if decision == "reject":
        status = "rejected"
    elif decision == "approve" and materials:
        status = "completed"
    elif ranked_jobs and not decision:
        status = "awaiting_review"
    else:
        status = "no_jobs"

    return jsonable_encoder(
        {
            "thread_id": thread_id,
            "status": status,
            "keyword": state.get("keyword"),
            "location": state.get("location"),
            "ranked_jobs": ranked_jobs,
            "application_materials": materials,
            "error": state.get("error") or None,
        }
    )


@app.get("/api/history")
def search_history(limit: int = 10):
    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100.",
        )

    history = get_recent_search_history(limit=limit)
    return jsonable_encoder({"history": history})
