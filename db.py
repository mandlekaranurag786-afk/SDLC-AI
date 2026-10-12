#db.py
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./requirements.db")

connect_args = {"check_same_thread": False, "timeout": 30} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class RequirementSession(Base):
    __tablename__ = "requirement_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    project_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_phase: Mapped[str] = mapped_column(String(50), default="decision")
    clarification_round: Mapped[int] = mapped_column(Integer, default=0)
    brd_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    frd_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_brd_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_frd_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    brd_docx_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    frd_docx_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    epics_stories_draft: Mapped[str | None] = mapped_column(Text, nullable=True)
    epics_stories_docx_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    estimation_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimation_docx_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prototype_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    prototype_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    conversation_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    extracted_requirements: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    requirement_completeness: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    pending_questions: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_report: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class ClarificationQA(Base):
    __tablename__ = "clarification_qa"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("requirement_sessions.id"), nullable=False)
    round: Mapped[int] = mapped_column(Integer, nullable=False)
    q_id: Mapped[str] = mapped_column(String(20), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    field: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_sqlite_columns()


def ensure_sqlite_columns() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return
    inspector = inspect(engine)
    if "requirement_sessions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("requirement_sessions")}
    if "owner_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN owner_id VARCHAR(100)"))
    if "project_name" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN project_name VARCHAR(100)"))
    if "extracted_requirements" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN extracted_requirements JSON"))
    if "requirement_completeness" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN requirement_completeness JSON"))
    if "estimation_report" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN estimation_report TEXT"))
    if "estimation_docx_path" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN estimation_docx_path VARCHAR(500)"))
    if "epics_stories_draft" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN epics_stories_draft TEXT"))
    if "epics_stories_docx_path" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN epics_stories_docx_path VARCHAR(500)"))
    if "prototype_html" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN prototype_html TEXT"))
    if "prototype_path" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE requirement_sessions ADD COLUMN prototype_path VARCHAR(500)"))
    if "clarification_qa" in inspector.get_table_names():
        qa_columns = {column["name"] for column in inspector.get_columns("clarification_qa")}
        if "field" not in qa_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE clarification_qa ADD COLUMN field VARCHAR(50)"))


@contextmanager
def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_requirement_session(db: Session, problem_statement: str, owner_id: str | None = None) -> RequirementSession:
    session = RequirementSession(problem_statement=problem_statement, owner_id=owner_id, conversation_history=[])
    db.add(session)
    db.flush()
    return session


def get_requirement_session(db: Session, session_id: str) -> RequirementSession | None:
    return db.get(RequirementSession, session_id)


def list_clarifications(db: Session, session_id: str) -> list[ClarificationQA]:
    with db.no_autoflush:
        return (
            db.query(ClarificationQA)
            .filter(ClarificationQA.session_id == session_id)
            .order_by(ClarificationQA.round.asc(), ClarificationQA.q_id.asc())
            .all()
        )


def add_pending_questions(
    db: Session,
    requirement_session: RequirementSession,
    round_number: int,
    questions_payload: dict[str, Any],
) -> None:
    requirement_session.clarification_round = round_number
    requirement_session.pending_questions = questions_payload
    requirement_session.current_phase = "clarification"
    for question in questions_payload.get("questions", []):
        db.add(
            ClarificationQA(
                session_id=requirement_session.id,
                round=round_number,
                q_id=question["id"],
                question=question["question"],
                category=question.get("category", "scope"),
                field=question.get("field"),
            )
        )


def save_answers(db: Session, session_id: str, round_number: int, answers: list[dict[str, str]]) -> None:
    answer_map = {item["q_id"]: item["answer"].strip() for item in answers}
    rows = (
        db.query(ClarificationQA)
        .filter(ClarificationQA.session_id == session_id, ClarificationQA.round == round_number)
        .all()
    )
    for row in rows:
        if row.q_id in answer_map:
            row.answer = answer_map[row.q_id]


def clarifications_as_dicts(db: Session, session_id: str) -> list[dict[str, Any]]:
    with db.no_autoflush:
        return [
            {
                "round": row.round,
                "q_id": row.q_id,
                "question": row.question,
                "answer": row.answer,
                "category": row.category,
                "field": row.field,
            }
            for row in list_clarifications(db, session_id)
        ]


def session_to_state(db: Session, requirement_session: RequirementSession) -> dict[str, Any]:
    with db.no_autoflush:
        return {
            "session_id": requirement_session.id,
            "problem_statement": requirement_session.problem_statement,
            "project_name": requirement_session.project_name,
            "clarification_rounds": clarifications_as_dicts(db, requirement_session.id),
            "brd_draft": requirement_session.brd_draft,
            "frd_draft": requirement_session.frd_draft,
            "is_brd_approved": requirement_session.is_brd_approved,
            "is_frd_approved": requirement_session.is_frd_approved,
            "conversation_history": requirement_session.conversation_history or [],
            "extracted_requirements": requirement_session.extracted_requirements,
            "requirement_completeness": requirement_session.requirement_completeness,
            "document_path": requirement_session.brd_docx_path or requirement_session.frd_docx_path,
            "brd_docx_path": requirement_session.brd_docx_path,
            "frd_docx_path": requirement_session.frd_docx_path,
            "epics_stories_draft": requirement_session.epics_stories_draft,
            "epics_stories_docx_path": requirement_session.epics_stories_docx_path,
            "estimation_report": requirement_session.estimation_report,
            "estimation_docx_path": requirement_session.estimation_docx_path,
            "prototype_html": requirement_session.prototype_html,
            "prototype_path": requirement_session.prototype_path,
            "current_phase": requirement_session.current_phase,
            "created_at": requirement_session.created_at.isoformat(),
            "updated_at": requirement_session.updated_at.isoformat(),
            "pending_questions": requirement_session.pending_questions,
            "validation_report": requirement_session.validation_report,
        }
