from typing import Any, List, Optional, TypedDict


class RequirementState(TypedDict, total=False):
    session_id: str
    problem_statement: str
    clarification_rounds: List[dict[str, Any]]
    brd_draft: Optional[str]
    frd_draft: Optional[str]
    document_path: Optional[str]
    brd_docx_path: Optional[str]
    frd_docx_path: Optional[str]
    epics_stories_draft: Optional[str]
    epics_stories_docx_path: Optional[str]
    estimation_report: Optional[str]
    estimation_docx_path: Optional[str]
    prototype_html: Optional[str]
    prototype_path: Optional[str]
    current_phase: str
    created_at: str
    updated_at: str
    extracted_requirements: Optional[dict[str, Any]]
    requirement_completeness: Optional[dict[str, Any]]
    pending_questions: Optional[dict[str, Any]]
    validation_report: Optional[dict[str, Any]]
    refinement_iterations: int
