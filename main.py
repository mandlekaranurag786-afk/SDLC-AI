import os
import traceback
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=True)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agent import (
    MAX_CLARIFICATION_ROUNDS,
    ensure_valid_problem_statement,
    generate_prototype,
    run_decision_and_maybe_questions,
    run_generation,
    serialize_preview,
)
from auth import verify_api_key
from db import (
    RequirementSession,
    add_pending_questions,
    clarifications_as_dicts,
    create_requirement_session,
    get_db,
    get_requirement_session,
    init_db,
    save_answers,
    session_to_state,
)
from llm import LLMServiceError


app = FastAPI(
    title="SDLC AI BRD/FRD Generation Agent",
    version="1.0.0",
    dependencies=[Depends(verify_api_key)]
)

allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,http://localhost:3000")
allowed_origins = [o.strip() for o in allowed_origins_str.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()
    from auth import get_valid_api_keys
    get_valid_api_keys()


@app.get("/health", include_in_schema=True)
@app.get("/api/health", include_in_schema=True)
def health_check():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    enable_traceback_logging = os.getenv("ENABLE_TRACEBACK_LOGGING", "false").lower() == "true"
    if enable_traceback_logging:
        try:
            log_dir = Path("logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "backend.log", "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now(timezone.utc).isoformat()}] Unhandled exception on {request.url.path}:\n")
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


class StartRequest(BaseModel):
    problem_statement: str = Field(..., min_length=1)


class AnswerItem(BaseModel):
    q_id: str
    answer: str = Field(..., min_length=1)


class AnswerQuestionsRequest(BaseModel):
    round: int
    answers: list[AnswerItem]


class GenerateRequest(BaseModel):
    approval_type: str = Field(default="both", pattern="^(brd|frd|both)$")


def db_dependency():
    with get_db() as db:
        yield db


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.post("/api/requirements/start")
def start_requirements(request: StartRequest, raw_request: Request):
    try:
        import time
        ensure_valid_problem_statement(request.problem_statement)
        owner_id = getattr(raw_request.state, "owner_id", None)

        with get_db() as db:
            past_session = (
                db.query(RequirementSession)
                .filter(
                    RequirementSession.owner_id == owner_id,
                    RequirementSession.problem_statement == request.problem_statement.strip()
                )
                .order_by(RequirementSession.created_at.desc())
                .first()
            )
            created_recently = past_session and (datetime.now(timezone.utc) - past_session.created_at.replace(tzinfo=timezone.utc)).total_seconds() < 120
            
            if created_recently:
                for _ in range(15):
                    db.refresh(past_session)
                    if past_session.current_phase != "requirement_analysis":
                        break
                    time.sleep(2)
                
                state = session_to_state(db, past_session)
                if state.get("pending_questions"):
                    return {
                        "session_id": past_session.id,
                        "status": "asking_questions",
                        "next_action": "answer_questions",
                        "questions": state["pending_questions"].get("questions", []),
                    }
                return {
                    "session_id": past_session.id,
                    "status": "ready_for_generation",
                    "next_action": "generate",
                    "questions": [],
                }

        with get_db() as db:
            requirement_session = create_requirement_session(db, request.problem_statement.strip(), owner_id=owner_id)
            session_id = requirement_session.id
            state = session_to_state(db, requirement_session)

        state = run_decision_and_maybe_questions(state)

        if state.get("pending_questions"):
            with get_db() as db:
                requirement_session = require_session(db, session_id)
                apply_state(db, requirement_session, state)
                add_pending_questions(db, requirement_session, state["pending_questions"]["round"], state["pending_questions"])
            return {
                "session_id": session_id,
                "status": "asking_questions",
                "next_action": "answer_questions",
                "questions": state["pending_questions"]["questions"],
            }

        with get_db() as db:
            requirement_session = require_session(db, session_id)
            apply_state(db, requirement_session, state)
            requirement_session.current_phase = "ready_for_generation"
        return {
            "session_id": session_id,
            "status": "proceed_to_brd",
            "next_action": "proceed_to_brd",
            "questions": [],
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/requirements/{session_id}/answer-questions")
def answer_questions(
    session_id: str,
    request: AnswerQuestionsRequest,
):
    with get_db() as db:
        requirement_session = require_session(db, session_id)
        pending = requirement_session.pending_questions or {}
        expected_round = pending.get("round")

        if not expected_round:
            raise HTTPException(status_code=409, detail="This session is not currently waiting for answers.")

        expected_ids = {q["id"] for q in pending.get("questions", [])}
        actual_ids = {answer.q_id for answer in request.answers}

        if request.round != expected_round:
            raise HTTPException(status_code=400, detail=f"Expected answers for round {expected_round}.")
        if actual_ids != expected_ids:
            raise HTTPException(status_code=400, detail="All current-round questions must be answered before proceeding.")

        save_answers(db, session_id, request.round, [answer.model_dump() for answer in request.answers])
        requirement_session.pending_questions = None
        requirement_session.current_phase = "requirement_analysis"

    try:
        with get_db() as db:
            requirement_session = require_session(db, session_id)
            state = session_to_state(db, requirement_session)

        state = run_decision_and_maybe_questions(state)

        if state.get("pending_questions"):
            if request.round >= MAX_CLARIFICATION_ROUNDS:
                with get_db() as db:
                    requirement_session = require_session(db, session_id)
                    apply_state(db, requirement_session, state)
                    requirement_session.pending_questions = None
                    requirement_session.current_phase = "blocked"
                raise HTTPException(
                    status_code=400,
                    detail="Unable to gather sufficient detail. Please revise the problem statement with more context.",
                )
            with get_db() as db:
                requirement_session = require_session(db, session_id)
                apply_state(db, requirement_session, state)
                add_pending_questions(db, requirement_session, state["pending_questions"]["round"], state["pending_questions"])
            return {
                "session_id": session_id,
                "round": request.round,
                "status": "more_questions_needed",
                "next_questions": state["pending_questions"]["questions"],
            }

        with get_db() as db:
            requirement_session = require_session(db, session_id)
            apply_state(db, requirement_session, state)
            requirement_session.current_phase = "ready_for_generation"
        return {
            "session_id": session_id,
            "round": request.round,
            "status": "ready_for_generation",
            "next_questions": [],
        }
    except LLMServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/requirements/{session_id}/generate")
def generate_documents(
    session_id: str,
    request: GenerateRequest,
):
    try:
        with get_db() as db:
            requirement_session = require_session(db, session_id)
            if requirement_session.pending_questions:
                raise HTTPException(status_code=400, detail="Clarifying questions must be answered before generation.")
            state = session_to_state(db, requirement_session)
            requirement_session.current_phase = "brd_generation"

        state = run_generation(state)

        with get_db() as db:
            requirement_session = require_session(db, session_id)
            apply_state(db, requirement_session, state)

        validation_report = state.get("validation_report") or {}
        open_items_count = len(validation_report.get("issues", []))
        return {
            "session_id": session_id,
            "status": "generated_with_notes" if open_items_count else "generated",
            "quality_score": validation_report.get("scores", {}).get("overall_quality"),
            "open_items_count": open_items_count,
            "brd_doc": {
                "url": f"/api/requirements/{session_id}/download/brd",
                "preview": serialize_preview(state.get("brd_draft")),
            },
            "frd_doc": {
                "url": f"/api/requirements/{session_id}/download/frd",
                "preview": serialize_preview(state.get("frd_draft")),
            },
            "epics_stories_doc": {
                "url": f"/api/requirements/{session_id}/download/epics-stories",
                "preview": serialize_preview(state.get("epics_stories_draft"), limit=1000),
            }
            if state.get("epics_stories_draft")
            else None,
            "estimation_doc": {
                "url": f"/api/requirements/{session_id}/download/estimation",
                "preview": serialize_preview(state.get("estimation_report"), limit=1000),
            }
            if state.get("estimation_report")
            else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except LLMServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/requirements/{session_id}/download/estimation")
def download_estimation(session_id: str, db: Session = Depends(db_dependency)):
    requirement_session = require_session(db, session_id)
    path = requirement_session.estimation_docx_path

    if not path or not Path(path).exists():
        raise HTTPException(
            status_code=404,
            detail="Estimation document has not been generated yet. Call /generate first.",
        )

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(path).name,
    )


@app.get("/api/requirements/{session_id}/download/epics-stories")
def download_epics_stories(session_id: str, db: Session = Depends(db_dependency)):
    requirement_session = require_session(db, session_id)
    path = requirement_session.epics_stories_docx_path

    if not path or not Path(path).exists():
        raise HTTPException(
            status_code=404,
            detail="Epics & User Stories document has not been generated yet. Call /generate first.",
        )

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(path).name,
    )


@app.post("/api/requirements/{session_id}/prototype")
def generate_prototype_endpoint(session_id: str):
    try:
        with get_db() as db:
            requirement_session = require_session(db, session_id)
            if not requirement_session.frd_draft:
                raise HTTPException(
                    status_code=400,
                    detail="FRD must be generated before requesting a prototype. Call /generate first.",
                )
            state = session_to_state(db, requirement_session)

        state = generate_prototype(state)

        with get_db() as db:
            requirement_session = require_session(db, session_id)
            requirement_session.prototype_html = state.get("prototype_html")
            requirement_session.prototype_path = state.get("prototype_path")

        return {
            "session_id": session_id,
            "status": "prototype_generated",
            "prototype_url": f"/api/requirements/{session_id}/download/prototype",
            "message": "Static HTML wireframe prototype generated successfully.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except LLMServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/requirements/{session_id}/download/prototype")
def download_prototype(session_id: str, db: Session = Depends(db_dependency)):
    requirement_session = require_session(db, session_id)
    path = requirement_session.prototype_path

    if not path or not Path(path).exists():
        raise HTTPException(
            status_code=404,
            detail="Prototype has not been generated yet. Call /prototype first.",
        )

    return FileResponse(path, media_type="text/html", filename=Path(path).name)


@app.get("/api/requirements/{session_id}/download/{doc_type}")
def download_document(session_id: str, doc_type: str, db: Session = Depends(db_dependency)):
    requirement_session = require_session(db, session_id)
    if doc_type == "brd":
        path = requirement_session.brd_docx_path
    elif doc_type == "frd":
        path = requirement_session.frd_docx_path
    else:
        raise HTTPException(status_code=404, detail="Document type must be 'brd' or 'frd'.")

    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Document has not been generated yet.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(path).name,
    )


@app.get("/api/requirements/{session_id}")
def get_requirement_state(session_id: str, raw_request: Request, db: Session = Depends(db_dependency)):
    owner_id = getattr(raw_request.state, "owner_id", None)
    requirement_session = require_session(db, session_id, current_owner_id=owner_id)
    return {
        "session_id": requirement_session.id,
        "problem_statement": requirement_session.problem_statement,
        "project_name": requirement_session.project_name,
        "current_phase": requirement_session.current_phase,
        "clarification_history": clarifications_as_dicts(db, session_id),
        "brd_draft": requirement_session.brd_draft,
        "frd_draft": requirement_session.frd_draft,
        "epics_stories_draft": requirement_session.epics_stories_draft,
        "created_at": requirement_session.created_at.isoformat(),
        "updated_at": requirement_session.updated_at.isoformat(),
    }


def require_session(db: Session, session_id: str, current_owner_id: str | None = None) -> RequirementSession:
    requirement_session = get_requirement_session(db, session_id)
    if not requirement_session:
        raise HTTPException(status_code=404, detail="Requirement session not found.")
    if current_owner_id and requirement_session.owner_id and requirement_session.owner_id != current_owner_id:
        raise HTTPException(status_code=404, detail="Requirement session not found.")
    return requirement_session


def apply_state(db: Session, requirement_session: RequirementSession, state: dict) -> None:
    requirement_session.current_phase = state.get("current_phase", requirement_session.current_phase)
    requirement_session.brd_draft = state.get("brd_draft", requirement_session.brd_draft)
    requirement_session.frd_draft = state.get("frd_draft", requirement_session.frd_draft)
    requirement_session.brd_docx_path = state.get("brd_docx_path", requirement_session.brd_docx_path)
    requirement_session.frd_docx_path = state.get("frd_docx_path", requirement_session.frd_docx_path)
    requirement_session.epics_stories_draft = state.get(
        "epics_stories_draft", requirement_session.epics_stories_draft
    )
    requirement_session.epics_stories_docx_path = state.get(
        "epics_stories_docx_path", requirement_session.epics_stories_docx_path
    )
    requirement_session.extracted_requirements = state.get(
        "extracted_requirements", requirement_session.extracted_requirements
    )
    requirement_session.requirement_completeness = state.get(
        "requirement_completeness", requirement_session.requirement_completeness
    )
    requirement_session.validation_report = state.get("validation_report", requirement_session.validation_report)
    requirement_session.estimation_report = state.get("estimation_report", requirement_session.estimation_report)
    requirement_session.estimation_docx_path = state.get(
        "estimation_docx_path", requirement_session.estimation_docx_path
    )
    requirement_session.prototype_html = state.get("prototype_html", requirement_session.prototype_html)
    requirement_session.prototype_path = state.get("prototype_path", requirement_session.prototype_path)
    requirement_session.conversation_history = state.get(
        "conversation_history", requirement_session.conversation_history or []
    )
    db.flush()
