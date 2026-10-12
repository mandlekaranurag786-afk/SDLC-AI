from typing import Any

import streamlit as st

from api_client import answer_questions, generate_documents, get_session_state, start_requirements


DEFAULT_STATE = {
    "session_id": None,
    "problem_statement": None,
    "current_phase": None,
    "clarification_rounds": 0,
    "clarification_history": [],
    "pending_questions": [],
    "brd_draft": None,
    "frd_draft": None,
    "brd_docx_url": None,
    "frd_docx_url": None,
    "epics_stories_draft": None,
    "estimation_report": None,
    "prototype_status": None,
    "prototype_url": None,
    "generated_at": None,
    "api_error": None,
    "loading": False,
    "last_status_message": None,
}


def init_session_state() -> None:
    for key, value in DEFAULT_STATE.items():
        if key not in st.session_state:
            st.session_state[key] = value.copy() if isinstance(value, list) else value


def reset_state() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_session_state()
    st.session_state.epics_stories_draft = None
    st.session_state.estimation_report = None
    st.session_state.prototype_status = None
    st.session_state.prototype_url = None


def set_api_error(error: Exception | str) -> None:
    st.session_state.api_error = str(error)
    st.session_state.loading = False


def submit_problem(problem_statement: str) -> None:
    st.session_state.loading = True
    st.session_state.api_error = None
    result = start_requirements(problem_statement)
    st.session_state.session_id = result.get("session_id")
    st.session_state.problem_statement = problem_statement
    st.session_state.pending_questions = result.get("questions", [])
    st.session_state.clarification_rounds = _round_from_questions(result.get("questions", [])) or 1

    if result.get("status") == "asking_questions":
        st.session_state.current_phase = "clarification"
        st.session_state.last_status_message = "Additional clarification needed. Please move to the Clarifying Q&A tab."
    else:
        st.session_state.current_phase = "generation"
        st.session_state.last_status_message = "Problem statement is clear. Move to Documents tab to generate BRD and FRD."
    st.session_state.loading = False


def submit_answers(answers_by_id: dict[str, str]) -> None:
    st.session_state.loading = True
    st.session_state.api_error = None
    pending_questions = st.session_state.pending_questions or []
    answers = [{"q_id": q_id, "answer": answer.strip()} for q_id, answer in answers_by_id.items()]
    result = answer_questions(st.session_state.session_id, st.session_state.clarification_rounds, answers)

    st.session_state.clarification_history.append(
        {
            "round": st.session_state.clarification_rounds,
            "answers": [
                {
                    "q_id": question["id"],
                    "question": question["question"],
                    "answer": answers_by_id.get(question["id"], "").strip(),
                }
                for question in pending_questions
            ],
        }
    )

    status = result.get("status")
    if status == "more_questions_needed":
        st.session_state.current_phase = "clarification"
        st.session_state.pending_questions = result.get("next_questions", [])
        st.session_state.clarification_rounds = _round_from_questions(result.get("next_questions", [])) or (
            st.session_state.clarification_rounds + 1
        )
        st.session_state.last_status_message = "Round complete. Next set of questions is ready."
    else:
        st.session_state.current_phase = "generation"
        st.session_state.pending_questions = []
        st.session_state.last_status_message = "All information gathered. Move to Documents tab to generate BRD and FRD."
    st.session_state.loading = False


def generate_brd_frd() -> None:
    st.session_state.loading = True
    st.session_state.api_error = None
    result = generate_documents(st.session_state.session_id)
    if result.get("status") == "validation_failed":
        st.session_state.api_error = f"Validation failed: {result.get('validation_report')}"
        st.session_state.loading = False
        return

    st.session_state.brd_draft = result.get("brd_doc", {}).get("preview")
    st.session_state.frd_draft = result.get("frd_doc", {}).get("preview")
    st.session_state.brd_docx_url = result.get("brd_doc", {}).get("url")
    st.session_state.frd_docx_url = result.get("frd_doc", {}).get("url")
    estimation_doc = result.get("estimation_doc")
    if estimation_doc:
        st.session_state.estimation_report = estimation_doc.get("preview", "")
    epics_stories_doc = result.get("epics_stories_doc")
    if epics_stories_doc:
        st.session_state.epics_stories_draft = epics_stories_doc.get("preview", "")
    st.session_state.generated_at = result.get("generated_at")
    st.session_state.current_phase = "complete"
    st.session_state.last_status_message = "Generation complete."
    st.session_state.loading = False


def refresh_session() -> dict[str, Any] | None:
    if not st.session_state.session_id:
        return None
    result = get_session_state(st.session_state.session_id)
    st.session_state.problem_statement = result.get("problem_statement")
    backend_phase = result.get("current_phase")
    if backend_phase == "complete":
        st.session_state.current_phase = "complete"
    st.session_state.clarification_history = _group_history(result.get("clarification_history", []))
    st.session_state.brd_draft = result.get("brd_draft") or st.session_state.brd_draft
    st.session_state.frd_draft = result.get("frd_draft") or st.session_state.frd_draft
    st.session_state.epics_stories_draft = result.get("epics_stories_draft") or st.session_state.epics_stories_draft
    return result


def _round_from_questions(questions: list[dict[str, Any]]) -> int | None:
    if not questions:
        return None
    return questions[0].get("round")


def _group_history(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("answer"):
            grouped.setdefault(row.get("round", 0), []).append(
                {
                    "q_id": row.get("q_id"),
                    "question": row.get("question"),
                    "answer": row.get("answer"),
                }
            )
    return [{"round": round_num, "answers": answers} for round_num, answers in sorted(grouped.items())]
