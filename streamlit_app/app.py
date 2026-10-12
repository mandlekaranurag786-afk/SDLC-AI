#app.py
import streamlit as st

from api_client import download_docx
from config import API_BASE_URL
from state_manager import (
    generate_brd_frd,
    init_session_state,
    refresh_session,
    reset_state,
    set_api_error,
    submit_answers,
    submit_problem,
)
from ui_components import (
    count_functional_requirements,
    render_header,
    render_previous_answers,
    render_sidebar,
    render_status,
    render_tabs,
)


st.set_page_config(
    page_title="SDLC AI - BRD/FRD Generator",
    page_icon="SDLC",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
        .stTextArea textarea { font-size: 0.95rem; }
        [data-testid="stMetricLabel"] {
            display: flex;
            justify-content: center;
            align-items: center;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def main() -> None:
    init_session_state()
    render_header()
    render_sidebar()
    render_status()

    tabs = render_tabs()
    with tabs[0]:
        render_problem_tab()

    if st.session_state.current_phase == "clarification" and len(tabs) > 1:
        with tabs[1]:
            render_clarification_tab()

    if st.session_state.current_phase in ["generation", "complete"]:
        doc_tab = tabs[-1]
        with doc_tab:
            render_documents_tab()


def render_problem_tab() -> None:
    st.subheader("Problem Statement")
    st.write(
        "Enter your project's problem statement. The AI agent will evaluate if it needs "
        "clarifying questions to generate comprehensive BRD and FRD documents."
    )

    is_read_only = bool(st.session_state.session_id)
    value = st.session_state.problem_statement or ""
    problem_statement = st.text_area(
        "Problem Statement",
        value=value,
        placeholder="Example: We need a system that allows construction estimators to upload tender PDFs...",
        height=150,
        key="problem_input",
        disabled=is_read_only,
    )

    if not is_read_only:
        start_disabled = st.session_state.get("loading", False) or st.session_state.get("start_inprogress", False)
        if st.button("Analyze & Start", key="submit_btn", use_container_width=True, disabled=start_disabled):
            if st.session_state.get("start_inprogress"): return
            if st.session_state.get("session_id"): return
            if not problem_statement.strip():
                st.error("Please enter a problem statement before starting.")
                return
            try:
                st.session_state.start_inprogress = True
                with st.spinner("Evaluating problem statement..."):
                    submit_problem(problem_statement.strip())
                st.rerun()
            except Exception as exc:
                set_api_error(exc)
                st.rerun()
            finally:
                st.session_state.start_inprogress = False
    else:
        st.info("This problem statement is locked for the current session.")
        if st.button("Reset", use_container_width=True):
            reset_state()
            st.rerun()

    if st.session_state.session_id:
        with st.expander("Session Details"):
            st.write(f"Session ID: {st.session_state.session_id}")
            st.write(f"Current Phase: {st.session_state.current_phase}")
            if st.button("Refresh Session Status"):
                try:
                    refresh_session()
                    st.rerun()
                except Exception as exc:
                    set_api_error(exc)
                    st.rerun()


def render_clarification_tab() -> None:
    st.subheader("Clarifying Questions")
    st.write(
        "The agent needs more information to generate accurate BRD/FRD documents. "
        "Please answer the following questions."
    )
    st.info(f"Round {st.session_state.clarification_rounds} of 5")

    pending_questions = st.session_state.pending_questions or []
    if not pending_questions:
        st.warning("No pending questions are available. Refresh the session or start a new project.")
        return

    with st.form(key=f"clarification_form_{st.session_state.clarification_rounds}"):
        answers_dict = {}
        for question in pending_questions:
            answer = st.text_area(
                label=f"{question['id']}. {question['question']}",
                placeholder="Enter your answer here...",
                height=80,
                key=f"answer_round_{st.session_state.clarification_rounds}_{question['id']}",
            )
            answers_dict[question["id"]] = answer

        submitted = st.form_submit_button("Submit Answers", use_container_width=True)
        if submitted:
            if any(not answer.strip() for answer in answers_dict.values()):
                st.error("Please answer all 5 questions before proceeding.")
            else:
                try:
                    with st.spinner("Processing your answers..."):
                        submit_answers(answers_dict)
                    st.rerun()
                except Exception as exc:
                    set_api_error(exc)
                    st.rerun()

    render_previous_answers()

    if st.button("Back to Problem Statement"):
        st.info("Use the Problem Statement tab above to review the locked session input.")


def render_documents_tab() -> None:
    st.subheader("Generated Documents")
    st.write("Preview generated BRD and FRD content below, then download the Word documents.")

    if st.session_state.current_phase == "generation" and not st.session_state.brd_draft:
        if st.button("Generate BRD & FRD", key="generate_btn", use_container_width=True):
            try:
                with st.spinner("Generating BRD, Epics & Stories, FRD and Project Estimation..."):
                    generate_brd_frd()
                st.rerun()
            except Exception as exc:
                set_api_error(exc)
                st.rerun()

    if st.session_state.brd_draft and st.session_state.frd_draft:
        fr_count = count_functional_requirements(st.session_state.frd_draft)
        st.success(
            f"""
            **Generation Complete**

            - **BRD Sections:** Executive Summary, Scope, Stakeholders, Success Criteria, Assumptions & Risks
            - **FRD Items:** {fr_count} functional requirements
            - **Epics & Stories:** Product backlog ready for Jira/Azure DevOps import
            - **Estimation:** Timeline, team structure and cost estimate generated
            - **Generated:** {st.session_state.generated_at or "Available"}
            """
        )

        col1, col2, col3, col4 = st.columns([1.2, 1.2, 1.5, 1.2])
        with col1:
            st.subheader("BRD")
            with st.expander("Preview BRD", expanded=False):
                st.markdown(st.session_state.brd_draft)
            render_download_button("brd", "Download BRD (Word)", "BRD.docx")

        with col2:
            st.subheader("FRD")
            with st.expander("Preview FRD", expanded=False):
                st.markdown(st.session_state.frd_draft)
            render_download_button("frd", "Download FRD (Word)", "FRD.docx")

        with col3:
            st.subheader("Epics & Stories")
            if st.session_state.get("epics_stories_draft"):
                with st.expander("Preview Epics & Stories", expanded=False):
                    st.markdown(st.session_state.epics_stories_draft)
                render_epics_stories_download_button()
            else:
                st.info("Generated automatically with BRD & FRD.")

        with col4:
            st.subheader("Estimation")
            if st.session_state.estimation_report:
                with st.expander("Preview Estimation", expanded=False):
                    st.markdown(st.session_state.estimation_report)
                render_estimation_download_button()
            else:
                st.info("Estimation is generated automatically with BRD & FRD.")

        st.divider()
        render_prototype_section()
        st.divider()

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            if st.button("Start New Project", use_container_width=True):
                reset_state()
                st.rerun()
        with col_b:
            if st.button("View Full Summary", use_container_width=True):
                st.session_state.show_summary = not st.session_state.get("show_summary", False)
        with col_c:
            if st.button("View Analytics", use_container_width=True):
                st.session_state.show_analytics = not st.session_state.get("show_analytics", False)

        if st.session_state.get("show_summary"):
            render_full_summary()
        if st.session_state.get("show_analytics"):
            render_analytics()


def render_download_button(doc_type: str, label: str, file_name: str) -> None:
    try:
        data = download_docx(st.session_state.session_id, doc_type)
        st.download_button(
            label=label,
            data=data,
            file_name=file_name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"Download failed: {exc}")
        fallback = st.session_state.brd_draft if doc_type == "brd" else st.session_state.frd_draft
        st.download_button(
            label=f"Download {doc_type.upper()} Markdown",
            data=fallback or "",
            file_name=f"{doc_type.upper()}.md",
            mime="text/markdown",
            use_container_width=True,
        )


def render_estimation_download_button() -> None:
    """Download button for the estimation .docx file."""
    try:
        from api_client import download_estimation

        data = download_estimation(st.session_state.session_id)
        st.download_button(
            label="Download Estimation (Word)",
            data=data,
            file_name="Project_Estimation.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"Estimation download failed: {exc}")
        if st.session_state.estimation_report:
            st.download_button(
                label="Download Estimation (Markdown)",
                data=st.session_state.estimation_report or "",
                file_name="Project_Estimation.md",
                mime="text/markdown",
                use_container_width=True,
            )


def render_epics_stories_download_button() -> None:
    """Download button for the Epics & User Stories .docx file."""
    try:
        from api_client import download_epics_stories

        data = download_epics_stories(st.session_state.session_id)
        st.download_button(
            label="Download Epics & Stories (Word)",
            data=data,
            file_name="Epics_and_User_Stories.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )
    except Exception as exc:
        st.error(f"Epics & Stories download failed: {exc}")
        if st.session_state.get("epics_stories_draft"):
            st.download_button(
                label="Download Epics & Stories (Markdown)",
                data=st.session_state.epics_stories_draft or "",
                file_name="Epics_and_User_Stories.md",
                mime="text/markdown",
                use_container_width=True,
            )


def render_prototype_section() -> None:
    """Prototype wireframe generation section, shown after BRD/FRD are ready."""
    st.subheader("Basic Prototype")
    st.write(
        "Optionally generate a static HTML wireframe prototype based on the FRD. "
        "This is a visual wireframe only; no backend logic is included."
    )

    status = st.session_state.prototype_status

    if status is None:
        if st.button("Generate Prototype", key="prototype_btn", use_container_width=False):
            try:
                st.session_state.prototype_status = "generating"
                st.rerun()
            except Exception as exc:
                set_api_error(exc)
                st.rerun()

    elif status == "generating":
        try:
            with st.spinner("Generating HTML wireframe prototype... this may take a minute."):
                from api_client import generate_prototype

                result = generate_prototype(st.session_state.session_id)
                st.session_state.prototype_url = result.get("prototype_url")
                st.session_state.prototype_status = "ready"
            st.rerun()
        except Exception as exc:
            st.session_state.prototype_status = "error"
            set_api_error(exc)
            st.rerun()

    elif status == "ready":
        st.success("Prototype generated successfully.")

        col1, col2 = st.columns(2)
        with col1:
            prototype_download_url = (
                f"{API_BASE_URL.rstrip('/')}/api/requirements/"
                f"{st.session_state.session_id}/download/prototype"
            )
            st.link_button(
                "Open in Browser",
                url=prototype_download_url,
                use_container_width=True,
            )
        with col2:
            try:
                from api_client import download_prototype_html

                html_data = download_prototype_html(st.session_state.session_id)
                st.download_button(
                    label="Download HTML",
                    data=html_data,
                    file_name="prototype_wireframe.html",
                    mime="text/html",
                    use_container_width=True,
                )
            except Exception as exc:
                st.error(f"Prototype download failed: {exc}")

        if st.button("Regenerate Prototype", key="regen_prototype_btn"):
            st.session_state.prototype_status = None
            st.session_state.prototype_url = None
            st.rerun()

    elif status == "error":
        st.error("Prototype generation failed. Check the API connection and try again.")
        if st.button("Try Again", key="retry_prototype_btn"):
            st.session_state.prototype_status = None
            st.rerun()


def render_full_summary() -> None:
    with st.expander("Full Summary", expanded=True):
        st.write(f"**Session ID:** {st.session_state.session_id}")
        st.write(f"**Problem Statement:** {st.session_state.problem_statement}")
        st.write(f"**Rounds Answered:** {len(st.session_state.clarification_history)}")
        st.write(f"**Generated At:** {st.session_state.generated_at or 'TBD'}")


def render_analytics() -> None:
    with st.expander("Analytics", expanded=True):
        question_count = sum(len(item["answers"]) for item in st.session_state.clarification_history)
        fr_count = count_functional_requirements(st.session_state.frd_draft)
        col1, col2, col3 = st.columns(3)
        col1.metric("Questions Answered", question_count)
        col2.metric("Clarification Rounds", len(st.session_state.clarification_history))
        col3.metric("Functional Requirements", fr_count)


if __name__ == "__main__":
    main()
