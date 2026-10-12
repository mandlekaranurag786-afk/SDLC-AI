import re

import streamlit as st


def render_header() -> None:
    st.markdown("# SDLC AI - BRD/FRD Generator")
    st.markdown("*Intelligent Requirements Analysis & Document Generation*")
    st.divider()


def render_sidebar() -> None:
    with st.sidebar:
        st.title("About")
        st.markdown(
            """
            This tool automates generation of Business Requirement Documents and
            Functional Requirement Documents from a project problem statement.

            **How it works:**
            1. Submit the project problem statement
            2. Answer clarifying questions if needed
            3. Download professional BRD and FRD documents
            """
        )
        if st.session_state.session_id:
            st.divider()
            st.write("**Current Session ID**")
            st.code(st.session_state.session_id, language="plaintext")


def render_tabs():
    tab_list = ["Problem Statement"]
    if st.session_state.current_phase == "clarification":
        tab_list.append("Clarifying Q&A")
    if st.session_state.current_phase in ["generation", "complete"]:
        tab_list.append("Documents")
    return st.tabs(tab_list)


def render_status() -> None:
    if st.session_state.api_error:
        st.error(st.session_state.api_error)
    elif st.session_state.last_status_message:
        if st.session_state.current_phase in ["generation", "complete"]:
            st.success(st.session_state.last_status_message)
        else:
            st.info(st.session_state.last_status_message)


def render_previous_answers() -> None:
    if not st.session_state.clarification_history:
        return
    with st.expander("View Previous Answers"):
        for round_data in st.session_state.clarification_history:
            st.write(f"**Round {round_data['round']}**")
            for qa in round_data["answers"]:
                st.write(f"**Q:** {qa['question']}")
                st.write(f"**A:** {qa['answer']}")


def count_functional_requirements(frd_markdown: str | None) -> int:
    if not frd_markdown:
        return 0
    return len(set(re.findall(r"FR-\d{3}", frd_markdown)))
