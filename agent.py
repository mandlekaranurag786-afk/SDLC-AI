#agent.py
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from document_export import export_documents
from llm import call_llm
from prompts import (
    BRD_PROMPT,
    BRD_FRD_CORRECTION_PROMPT,
    CLARIFICATION_PROMPT,
    EPICS_STORIES_PROMPT,
    FRD_PROMPT,
    PROJECT_ESTIMATION_PROMPT,
    PROTOTYPE_PROMPT,
    REQUIREMENT_ANALYSIS_PROMPT,
    VALIDATION_PROMPT,
)
from state_schema import RequirementState


MAX_CLARIFICATION_ROUNDS = 5
QUESTIONS_PER_ROUND = 5
MAX_REFINEMENT_ITERATIONS = 2
REQUIRED_REQUIREMENT_FIELDS = [
    "business_objective",
    "current_process",
    "pain_points",
    "stakeholders",
    "functional_features",
    "user_workflows",
    "integrations",
    "constraints",
    "success_metrics",
]


def format_clarification_history(history: list[dict[str, Any]]) -> str:
    if not history:
        return "None"
    lines = []
    for item in history:
        answer = item.get("answer") or "Unanswered"
        lines.append(f"Round {item.get('round')} {item.get('q_id')}: {item.get('question')}\nAnswer: {answer}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Token-reduction helpers — extract compact summaries from BRD/FRD
# before sending to downstream LLM calls
# ---------------------------------------------------------------------------

def _extract_brd_for_epics(brd: str) -> str:
    """
    Return Executive Summary + In Scope list from BRD only.
    Epics agent does not need the full BRD prose (~400 tokens vs ~2500).
    """
    lines = brd.splitlines()
    result: list[str] = []
    capture = False
    current_num = ""
    targets = {"1", "2", "5", "5.1"}

    for line in lines:
        m = re.match(r"^#{2,3}\s+(\d+(?:\.\d+)?)[\.\s]", line.strip())
        if m:
            current_num = m.group(1)
            capture = current_num in targets
        if capture:
            result.append(line)

    extracted = "\n".join(result).strip()
    return extracted if len(extracted) > 200 else brd[:1500]


def _extract_brd_for_frd(brd: str) -> str:
    """
    Return only Section 5.1 In Scope from BRD for FRD generation.
    FRD needs the capability list, not full prose (~300 tokens vs ~2500).
    """
    match = re.search(
        r"(?m)^#{2,3}\s+5\.1[^#\n]*\n(.*?)(?=^#{2,3}\s+5\.2|^#{2,3}\s+6\.|^#{2}\s+\d+\.|\Z)",
        brd,
        re.DOTALL,
    )
    if match:
        return f"## 5.1 In Scope\n{match.group(1).strip()}"
    return brd[:800]


def _extract_brd_for_estimation(brd: str) -> str:
    """
    Return Sections 1, 3, 8, 11 from BRD for estimation.
    Estimation needs objectives, constraints, success criteria (~600 tokens vs ~2500).
    """
    lines = brd.splitlines()
    result: list[str] = []
    capture = False
    targets = {"1", "3", "8", "11"}

    for line in lines:
        m = re.match(r"^#{2,3}\s+(\d+(?:\.\d+)?)[\.\s]", line.strip())
        if m:
            capture = m.group(1) in targets
        if capture:
            result.append(line)

    extracted = "\n".join(result).strip()
    return extracted if len(extracted) > 200 else brd[:1200]


def _extract_epics_titles_for_frd(epics: str) -> str:
    """
    Return only Epic headings + Story IDs + Story titles from Epics document.
    FRD only needs these for traceability reference (~400 tokens vs ~2500).
    """
    lines = epics.splitlines()
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^##\s+E-\d{3}:", stripped):
            result.append(stripped)
        elif re.match(r"^###\s+US-\d{3}:", stripped):
            result.append(stripped)
        elif stripped.startswith("As a ") or stripped.startswith("**User Story:**"):
            result.append(stripped)
    extracted = "\n".join(result).strip()
    return extracted if len(extracted) > 100 else "Not yet generated."


def _extract_frd_for_validation(frd: str) -> str:
    """
    Return FR IDs, titles, business rules, acceptance criteria from FRD.
    Python validator already handles structure; LLM validates semantics only.
    (~2000 tokens vs ~4000).
    """
    fr_blocks = parse_functional_requirements(frd)
    result: list[str] = []
    for block in fr_blocks:
        result.append(f"## {block['id']}: {block['title']}")
        rules = extract_section_items(block["text"], "Business Rules")
        if rules:
            result.append("**Business Rules:**")
            for rule in rules[:3]:
                result.append(f"- {rule}")
        criteria = extract_section_items(block["text"], "Acceptance Criteria")
        if criteria:
            result.append("**Acceptance Criteria:**")
            for criterion in criteria[:2]:
                result.append(f"- {criterion}")
        traceability_match = re.search(r"Maps to BRD Section:\s*([^\n]+)", block["text"])
        if traceability_match:
            result.append(f"**Traceability:** {traceability_match.group(1).strip()}")
        result.append("")
    extracted = "\n".join(result).strip()
    return extracted if len(extracted) > 200 else frd[:3000]


def _extract_frd_for_estimation(frd: str) -> str:
    """
    Return FR IDs, titles, priorities, dependencies for estimation.
    Estimation needs to count and categorise FRs, not read full detail.
    (~800 tokens vs ~4000).
    """
    fr_blocks = parse_functional_requirements(frd)
    result: list[str] = []
    for block in fr_blocks:
        priority_match = re.search(r"\*\*Priority:\*\*\s*(\w+)", block["text"])
        priority = priority_match.group(1) if priority_match else "TBD"
        result.append(f"- {block['id']}: {block['title']} | Priority: {priority}")
    extracted = "\n".join(result).strip()
    return extracted if len(extracted) > 100 else frd[:2000]


def analyze_requirements(state: RequirementState) -> RequirementState:
    prompt = REQUIREMENT_ANALYSIS_PROMPT.format(
        problem_statement=state["problem_statement"],
        clarification_history=format_clarification_history(state.get("clarification_rounds", [])),
    )
    analysis = call_llm(prompt, expect_json=True)
    requirements = analysis.get("requirements") if isinstance(analysis.get("requirements"), dict) else {}
    completeness = analysis.get("completeness") if isinstance(analysis.get("completeness"), dict) else {}
    state["extracted_project_name"] = str(analysis.get("project_name") or "")

    # Completeness is judged fresh by the LLM every round, which has no
    # natural stopping point for open-ended fields (integrations, features,
    # constraints, etc.) and can re-flag an already-answered field as
    # incomplete indefinitely. Once a field is COMPLETE, it stays COMPLETE —
    # never let a later round regress it, regardless of what the fresh
    # judgment says.
    previous_requirements = state.get("extracted_requirements") or {}
    requirements = _lock_in_previously_complete_fields(
        previous_requirements,
        requirements,
        clarification_rounds=state.get("clarification_rounds", []),
    )

    state["extracted_requirements"] = requirements
    state["requirement_completeness"] = normalize_completeness_report(
        completeness,
        requirements,
    )
    state["current_phase"] = "requirement_analysis"
    return state


def _fields_answered_in_history(clarification_rounds: list[dict[str, Any]]) -> dict[str, str]:
    """
    Return {field: latest_non_empty_answer} for every requirement field
    that was actually asked about and answered. This treats affirmative
    answers and exclusionary answers like "no integration needed" equally.
    """
    answered: dict[str, str] = {}
    for item in clarification_rounds:
        field = item.get("field")
        answer = item.get("answer")
        if field in REQUIRED_REQUIREMENT_FIELDS and isinstance(answer, str) and answer.strip():
            answered[field] = answer.strip()
    return answered


def _lock_in_previously_complete_fields(
    previous: dict[str, Any],
    current: dict[str, Any],
    clarification_rounds: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Prevent a field from regressing from COMPLETE to PARTIAL/MISSING across
    rounds, and force-complete any field that was actually asked about and
    given a non-empty answer in a prior clarification round. This avoids
    repeating a question when the user's definitive answer was negative,
    but the extraction model represented it as an empty value.
    """
    answered_fields = _fields_answered_in_history(clarification_rounds)

    for field in REQUIRED_REQUIREMENT_FIELDS:
        previous_entry = previous.get(field) if isinstance(previous.get(field), dict) else {}
        current_entry = current.get(field) if isinstance(current.get(field), dict) else {}
        previous_status = previous_entry.get("status")
        current_status = current_entry.get("status")

        if previous_status == "COMPLETE":
            # Never regress a field that was already complete.
            current[field] = current_entry if current_status == "COMPLETE" else previous_entry
            continue

        if current_status == "COMPLETE":
            continue  # freshly complete this round, nothing to do

        if field in answered_fields:
            merged_entry = dict(current_entry) if current_entry else dict(previous_entry)
            merged_entry["status"] = "COMPLETE"
            if not has_value(merged_entry.get("value")):
                merged_entry["value"] = answered_fields[field]
            current[field] = merged_entry
            continue

        current[field] = current_entry or previous_entry

    return current


def generate_clarifying_questions(state: RequirementState) -> RequirementState:
    round_number = 1 + max([item.get("round", 0) for item in state.get("clarification_rounds", [])] or [0])
    missing_fields = state.get("requirement_completeness", {}).get("missing_fields", [])
    extracted_requirements = state.get("extracted_requirements") or {}
    prompt = CLARIFICATION_PROMPT.format(
        problem_statement=state["problem_statement"],
        clarification_history=format_clarification_history(state.get("clarification_rounds", [])),
        known_information=json.dumps(build_known_information(extracted_requirements), indent=2),
        missing_information=json.dumps(build_missing_information(extracted_requirements, missing_fields), indent=2),
        missing_field_details=json.dumps(missing_fields, indent=2),
        round_number=round_number,
    )
    payload = call_llm(prompt, expect_json=True)
    questions = normalize_clarifying_questions(payload.get("questions", []), missing_fields)
    payload["round"] = round_number
    payload["questions"] = questions
    state["pending_questions"] = payload
    state["current_phase"] = "clarification"
    return state


def generate_brd(state: RequirementState) -> RequirementState:
    from integration_utils import extract_structured_list, check_items_coverage, log_prompt_debug

    extracted = state.get("extracted_requirements") or {}
    integrations_raw = (extracted.get("integrations") or {}).get("value", "")
    integrations_list = extract_structured_list(integrations_raw)
    state["integrations"] = integrations_list

    clean_requirements = {
        field: {k: v for k, v in entry.items() if not k.startswith("_")}
        if isinstance(entry, dict) else entry
        for field, entry in extracted.items()
    }

    req_integrations_str = ", ".join(integrations_list) if integrations_list else "None specified"

    prompt = BRD_PROMPT.format(
        requirement_model=json.dumps(clean_requirements, indent=2),
        required_integrations=req_integrations_str,
    )

    log_prompt_debug("BRD", prompt)
    brd_draft = str(call_llm(prompt, max_tokens=5000))

    # Coverage Post-Check & Retry
    if integrations_list:
        present, missing = check_items_coverage(brd_draft, integrations_list)
        if missing:
            retry_prompt = prompt + f"\n\n[CRITICAL RETRY]: The previous draft missed these required integrations in Section 5.1: {', '.join(missing)}. YOU MUST INCLUDE EVERY ONE IN SECTION 5.1."
            log_prompt_debug("BRD_RETRY", retry_prompt)
            brd_draft = str(call_llm(retry_prompt, max_tokens=5000))
            present_after, still_missing = check_items_coverage(brd_draft, integrations_list)
            if still_missing:
                val_report = state.get("validation_report") or {"issues": [], "scores": {}, "is_valid": False}
                issues = val_report.get("issues", [])
                for item in still_missing:
                    issues.append({
                        "type": "missing_integration",
                        "severity": "HIGH",
                        "section": "BRD Section 5.1",
                        "affected_requirement": item,
                        "recommendation": f"Include required system integration '{item}' in Section 5.1 In Scope."
                    })
                val_report["issues"] = issues
                state["validation_report"] = val_report

    state["brd_draft"] = brd_draft
    state["current_phase"] = "brd_generation"
    return state


def generate_epics_stories(state: RequirementState) -> RequirementState:
    from arithmetic_utils import recompute_epics_arithmetic
    # Send only Executive Summary + In Scope instead of full BRD (~80% fewer tokens)
    brd_summary = _extract_brd_for_epics(state.get("brd_draft", ""))
    prompt = EPICS_STORIES_PROMPT.format(brd=brd_summary)
    draft = str(call_llm(prompt, max_tokens=7000))
    state["epics_stories_draft"] = recompute_epics_arithmetic(draft)
    state["current_phase"] = "epics_stories_generation"
    return state


def generate_frd(state: RequirementState) -> RequirementState:
    from integration_utils import extract_structured_list, check_items_coverage, log_prompt_debug

    extracted = state.get("extracted_requirements") or {}
    integrations_list = state.get("integrations") or extract_structured_list((extracted.get("integrations") or {}).get("value", ""))
    req_integrations_str = ", ".join(integrations_list) if integrations_list else "None specified"

    brd_scope = _extract_brd_for_frd(state.get("brd_draft", ""))
    epics_titles = _extract_epics_titles_for_frd(
        state.get("epics_stories_draft") or ""
    )

    prompt = FRD_PROMPT.format(
        requirement_model=json.dumps(extracted, indent=2),
        required_integrations=req_integrations_str,
        brd_from_previous_node=brd_scope,
        epics_stories=epics_titles,
    )

    log_prompt_debug("FRD", prompt)
    frd_draft = str(call_llm(prompt, max_tokens=7000))

    # Coverage Post-Check & Retry
    if integrations_list:
        present, missing = check_items_coverage(frd_draft, integrations_list)
        if missing:
            retry_prompt = prompt + f"\n\n[CRITICAL RETRY]: The previous draft missed functional requirements for these integrations: {', '.join(missing)}. YOU MUST ADD A DEDICATED FR FOR EACH ONE."
            log_prompt_debug("FRD_RETRY", retry_prompt)
            frd_draft = str(call_llm(retry_prompt, max_tokens=5000))
            present_after, still_missing = check_items_coverage(frd_draft, integrations_list)
            if still_missing:
                val_report = state.get("validation_report") or {"issues": [], "scores": {}, "is_valid": False}
                issues = val_report.get("issues", [])
                for item in still_missing:
                    issues.append({
                        "type": "missing_integration",
                        "severity": "HIGH",
                        "section": "FRD Functional Requirements",
                        "affected_requirement": item,
                        "recommendation": f"Add functional requirement covering system integration '{item}'."
                    })
                val_report["issues"] = issues
                state["validation_report"] = val_report

    state["frd_draft"] = frd_draft
    state["current_phase"] = "frd_generation"
    return state


def validate_completeness(state: RequirementState) -> RequirementState:
    brd = state.get("brd_draft", "")
    frd = state.get("frd_draft", "")

    # Python validator uses full documents for structural checks (no LLM cost)
    python_report = validate_documents_with_python(brd=brd, frd=frd)

    # LLM validator gets compact summary — Python already checked structure
    # ~2800 tokens input instead of ~6500 (57% reduction)
    brd_summary = _extract_brd_for_epics(brd)  # headings + scope sections
    frd_core = _extract_frd_for_validation(frd)  # titles + rules + criteria only
    prompt = VALIDATION_PROMPT.format(brd=brd_summary, frd=frd_core)
    llm_report = call_llm(prompt, expect_json=True)

    state["validation_report"] = normalize_validation_report(
        merge_validation_reports(python_report, llm_report)
    )
    state["current_phase"] = "validation"
    return state


def refine_documents(state: RequirementState) -> RequirementState:
    validation_report = state.get("validation_report") or {}
    prompt = BRD_FRD_CORRECTION_PROMPT.format(
        issues_formatted=json.dumps(validation_report.get("issues") or [], indent=2),
        brd_draft=state.get("brd_draft", ""),
        frd_draft=state.get("frd_draft", ""),
    )
    # Response contains two full regenerated documents inside a JSON object —
    # needs far more headroom than the 2000-token default, or the JSON gets
    # truncated mid-response and fails to parse on every retry.
    refined = call_llm(prompt, expect_json=True, max_tokens=12000)
    if refined.get("brd"):
        state["brd_draft"] = str(refined["brd"])
    if refined.get("frd"):
        state["frd_draft"] = str(refined["frd"])
    state["refinement_iterations"] = int(state.get("refinement_iterations") or 0) + 1
    state["current_phase"] = "refinement"
    return state


def _run_parallel_exports(state: RequirementState) -> RequirementState:
    session_id = state["session_id"]
    problem_statement = state["problem_statement"]
    project_name = derive_project_name(problem_statement)
    brd_draft = state.get("brd_draft") or ""
    frd_draft = state.get("frd_draft") or ""
    epics_draft = state.get("epics_stories_draft") or ""
    validation_report = state.get("validation_report") or {}
    validation_report_for_export = validation_report if should_export_with_notes(state) else None
    results: dict[str, Any] = {}

    def task_export_brd_frd() -> dict[str, str]:
        from document_export import export_documents

        brd_path, frd_path = export_documents(
            session_id=session_id,
            project_name=project_name,
            brd_markdown=brd_draft,
            frd_markdown=frd_draft,
            validation_report=validation_report_for_export,
        )
        return {"brd_docx_path": brd_path, "frd_docx_path": frd_path}

    def task_generate_and_export_estimation() -> dict[str, str]:
        from arithmetic_utils import recompute_estimation_cost, recompute_estimation_timeline
        from currency_utils import detect_budget
        from document_export import export_single_document
        from llm import call_llm
        from prompts import PROJECT_ESTIMATION_PROMPT

        # Send compact summaries instead of full documents
        # (~1400 tokens input vs ~6500 — 78% reduction)
        brd_for_est = _extract_brd_for_estimation(brd_draft)
        frd_for_est = _extract_frd_for_estimation(frd_draft)
        prompt = PROJECT_ESTIMATION_PROMPT.format(brd=brd_for_est, frd=frd_for_est)
        estimation_md = str(call_llm(prompt, max_tokens=4000))

        budget_text = str((state.get("extracted_requirements") or {}).get("constraints") or "") + " " + brd_for_est
        budget_amt, target_curr = detect_budget(budget_text)

        estimation_md = recompute_estimation_timeline(
            estimation_md,
            epics_draft
        )
        estimation_md = recompute_estimation_cost(
            estimation_md,
            target_currency=target_curr,
            user_budget=budget_amt
        )
        estimation_path = export_single_document(
            session_id=session_id,
            project_name=project_name,
            markdown_content=estimation_md,
            doc_type="estimation",
        )
        return {
            "estimation_report": estimation_md,
            "estimation_docx_path": estimation_path,
        }

    def task_export_epics() -> dict[str, str]:
        if not epics_draft:
            return {}
        from document_export import export_single_document

        epics_path = export_single_document(
            session_id=session_id,
            project_name=project_name,
            markdown_content=epics_draft,
            doc_type="epics_stories",
        )
        return {"epics_stories_docx_path": epics_path}

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(task_export_brd_frd): "brd_frd",
            executor.submit(task_generate_and_export_estimation): "estimation",
            executor.submit(task_export_epics): "epics",
        }
        for future in as_completed(futures):
            try:
                results.update(future.result())
            except Exception as exc:
                task_name = futures[future]
                print(f"[WARNING] Parallel task '{task_name}' failed: {exc}")

    state.update(results)
    state["document_path"] = results.get("brd_docx_path", state.get("document_path"))
    state["current_phase"] = "complete"
    return state


def generate_prototype(state: RequirementState) -> RequirementState:
    prompt = PROTOTYPE_PROMPT.format(
        prototype_context=build_prototype_context(state.get("frd_draft", "")),
    )
    html_content = str(call_llm(prompt, expect_json=False)).strip()
    if html_content.startswith("```"):
        lines = html_content.splitlines()
        html_content = "\n".join(lines[1:-1]) if lines and lines[-1].strip() == "```" else "\n".join(lines[1:])
    state["prototype_html"] = html_content

    output_dir = Path("outputs") / state["session_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    prototype_path = output_dir / "Prototype.html"
    prototype_path.write_text(html_content, encoding="utf-8")
    state["prototype_path"] = str(prototype_path)
    state["current_phase"] = "prototype_complete"
    return state


def build_prototype_context(frd: str) -> str:
    fr_blocks = parse_functional_requirements(frd)
    screens = infer_screens_from_requirements(fr_blocks)
    workflows = extract_numbered_sections(fr_blocks, "Main Workflow")
    context: dict[str, Any] = {
        "actors": sorted(extract_unique_section_items(fr_blocks, "Actors")),
        "screens": screens,
        "navigation": infer_navigation(screens),
        "forms": extract_form_requirements(fr_blocks),
        "tables": extract_table_requirements(fr_blocks),
        "dashboard_widgets": extract_dashboard_widgets(fr_blocks),
        "user_workflows": workflows,
        "alternative_workflows": extract_numbered_sections(fr_blocks, "Alternative Workflow"),
    }
    return json.dumps(context, indent=2)


def extract_unique_section_items(fr_blocks: list[dict[str, Any]], section_label: str) -> set[str]:
    items: set[str] = set()
    for block in fr_blocks:
        for item in extract_section_items(block["text"], section_label):
            cleaned = item.strip()
            if cleaned and cleaned.upper() != "TBD":
                items.add(cleaned)
    return items


def extract_numbered_sections(fr_blocks: list[dict[str, Any]], section_label: str) -> list[dict[str, Any]]:
    sections = []
    for block in fr_blocks:
        items = extract_section_items(block["text"], section_label)
        if items:
            sections.append(
                {
                    "requirement_id": block["id"],
                    "title": block["title"],
                    "steps": items[:8],
                }
            )
    return sections


def extract_form_requirements(fr_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    forms = []
    form_terms = re.compile(r"\b(form|input|field|submit|registration|profile|questionnaire|feedback)\b", re.IGNORECASE)
    for block in fr_blocks:
        inputs = extract_section_items(block["text"], "Inputs")
        if form_terms.search(block["title"]) or inputs:
            forms.append(
                {
                    "requirement_id": block["id"],
                    "title": block["title"],
                    "fields": [item for item in inputs if item.upper() != "TBD"][:12],
                    "submit_action": infer_primary_action(block["title"], block["text"]),
                }
            )
    return forms


def extract_table_requirements(fr_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables = []
    table_terms = re.compile(r"\b(table|list|records|search|filter|sort|pagination|grid|queue|dashboard)\b", re.IGNORECASE)
    for block in fr_blocks:
        outputs = extract_section_items(block["text"], "Outputs")
        if table_terms.search(block["title"]) or table_terms.search(block["text"]):
            columns = infer_table_columns(block["title"], block["text"], outputs)
            if columns:
                tables.append(
                    {
                        "requirement_id": block["id"],
                        "title": block["title"],
                        "columns": columns[:8],
                        "row_actions": infer_row_actions(block["text"])[:5],
                    }
                )
    return tables[:8]


def extract_dashboard_widgets(fr_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    widgets = []
    dashboard_terms = re.compile(r"\b(dashboard|analytics|report|metric|kpi|chart|summary)\b", re.IGNORECASE)
    for block in fr_blocks:
        if dashboard_terms.search(block["title"]) or dashboard_terms.search(block["text"]):
            widgets.append(
                {
                    "requirement_id": block["id"],
                    "title": block["title"],
                    "widgets": infer_dashboard_widgets(block["text"])[:8],
                }
            )
    return widgets[:8]


def infer_screens_from_requirements(fr_blocks: list[dict[str, Any]]) -> list[dict[str, str]]:
    screens = []
    for block in fr_blocks:
        title = block["title"]
        text = block["text"]
        if re.search(r"\b(api|integration|export|audit|encryption|background|notification)\b", title, re.IGNORECASE):
            continue
        if re.search(r"\b(dashboard|form|upload|review|approve|manage|profile|feedback|schedule|list|search|report)\b", text, re.IGNORECASE):
            description = extract_section_items(block["text"], "Description")
            screens.append(
                {
                    "screen_name": title,
                    "source_requirement": block["id"],
                    "purpose": (description[0] if description else first_sentence(strip_markdown(text)))[:240],
                    "primary_action": infer_primary_action(title, text),
                }
            )
    return screens[:8]


def infer_navigation(screens: list[dict[str, str]]) -> list[dict[str, str]]:
    navigation = [{"label": "Home", "target_screen": screens[0]["screen_name"] if screens else "Dashboard"}]
    seen = {"Home"}
    for screen in screens:
        label = re.sub(r"^(Manage|Create|View|Update)\s+", "", screen["screen_name"]).strip()
        label = label[:28] or screen["screen_name"]
        if label not in seen:
            navigation.append({"label": label, "target_screen": screen["screen_name"]})
            seen.add(label)
    return navigation[:8]


def infer_table_columns(title: str, text: str, outputs: list[str]) -> list[str]:
    candidates = outputs + extract_section_items(text, "Inputs")
    columns: list[str] = []
    for item in candidates:
        label = re.split(r":|-", item, maxsplit=1)[0].strip()
        label = re.sub(r"\b(output|input|data|field|parameter)\b", "", label, flags=re.IGNORECASE).strip()
        if label and label.upper() != "TBD":
            columns.append(label.title())
    if not columns:
        base = re.sub(r"\b(manage|view|list|search|dashboard|report)\b", "", title, flags=re.IGNORECASE).strip()
        entity = base or "Record"
        columns = [f"{entity} ID", "Name", "Status", "Owner", "Updated Date"]
    if "Status" not in columns:
        columns.append("Status")
    return dedupe_preserve_order(columns)


def infer_row_actions(text: str) -> list[str]:
    actions = []
    for verb in ["View", "Edit", "Approve", "Reject", "Assign", "Export", "Download", "Archive"]:
        if re.search(rf"\b{verb.lower()}|{verb}\b", text, re.IGNORECASE):
            actions.append(verb)
    return actions or ["View", "Edit"]


def infer_dashboard_widgets(text: str) -> list[str]:
    metrics = []
    for item in extract_section_items(text, "Outputs") + extract_section_items(text, "Acceptance Criteria"):
        if re.search(r"\b(metric|kpi|count|rate|score|status|trend|summary|chart|dashboard)\b", item, re.IGNORECASE):
            metrics.append(strip_markdown(item)[:120])
    return dedupe_preserve_order(metrics) or ["Summary metrics", "Status breakdown", "Recent activity"]


def infer_primary_action(title: str, text: str) -> str:
    action_patterns = [
        (r"upload(?:s|ed|ing)?", "Upload"),
        (r"submit(?:s|ted|ting)?", "Submit"),
        (r"approve(?:s|d|ing)?", "Approve"),
        (r"review(?:s|ed|ing)?", "Review"),
        (r"schedule(?:s|d|ing)?", "Schedule"),
        (r"export(?:s|ed|ing)?", "Export"),
        (r"search(?:es|ed|ing)?", "Search"),
        (r"assign(?:s|ed|ing)?", "Assign"),
        (r"generate(?:s|d|ing)?", "Generate"),
        (r"manage(?:s|d|ing)?", "Manage"),
    ]
    combined = f"{title} {text}".lower()
    for pattern, label in action_patterns:
        if re.search(rf"\b{pattern}\b", combined):
            return label
    return "Continue"


def dedupe_preserve_order(items: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            deduped.append(normalized)
            seen.add(key)
    return deduped


def extract_section_items(text: str, section_label: str) -> list[str]:
    pattern = rf"\*\*{re.escape(section_label)}:\*\*\s*(.*?)(?=\n\*\*[^*\n]+:\*\*|\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return []
    body = match.group(1).strip()
    items = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[-*]\s+", "", stripped)
        stripped = re.sub(r"^\d+\.\s+", "", stripped)
        if stripped:
            items.append(stripped)
    return items


def strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"[-*]\s+", "", text)
    return " ".join(text.split())


def first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return parts[0] if parts else text


def run_decision_and_maybe_questions(state: RequirementState) -> RequirementState:
    state = analyze_requirements(state)
    if state.get("requirement_completeness", {}).get("ready_for_generation"):
        state["current_phase"] = "ready_for_generation"
        return state
    return generate_clarifying_questions(state)


def run_generation(state: RequirementState) -> RequirementState:
    from deterministic_checks import run_deterministic_checks
    state["refinement_iterations"] = 0
    state = generate_brd(state)
    state = generate_epics_stories(state)
    state = generate_frd(state)
    while True:
        state = validate_completeness(state)
        run_deterministic_checks(state)
        action = classify_validation_severity(state.get("validation_report") or {})
        state["validation_action"] = action
        if action == "proceed":
            return _run_parallel_exports(state)
        if int(state.get("refinement_iterations") or 0) >= max_refinement_iterations_for_validation(
            state.get("validation_report") or {}
        ):
            return _run_parallel_exports(state)
        state = refine_documents(state)


def derive_project_name(
    problem_statement: str,
    user_provided_name: str | None = None,
    extracted_name: str | None = None
) -> str:
    from project_name_utils import resolve_project_name
    return resolve_project_name(
        user_provided_name=user_provided_name,
        extracted_name=extracted_name,
        problem_statement=problem_statement
    )


def ensure_valid_problem_statement(problem_statement: str) -> None:
    sentences = [part for part in problem_statement.replace("\n", " ").split(".") if part.strip()]
    if len(problem_statement.split()) < 12 or len(sentences) < 1:
        raise ValueError(
            "Problem statement is too vague. Please provide at least 2-3 sentences with business objective and primary users."
        )


def serialize_preview(markdown: str | None, limit: int = 4000) -> str:
    if not markdown:
        return ""
    return markdown[:limit]


def pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2)


def normalize_validation_report(report: dict[str, Any]) -> dict[str, Any]:
    scores = report.get("scores") if isinstance(report.get("scores"), dict) else {}
    normalized_scores = {
        "overall_quality": normalize_score(scores.get("overall_quality"), 0),
        "requirement_mapping": normalize_score(scores.get("requirement_mapping"), 0),
        "constraint_coverage": normalize_score(scores.get("constraint_coverage"), 0),
        "traceability": normalize_score(scores.get("traceability"), 0),
        "consistency": normalize_score(scores.get("consistency"), 0),
    }
    issues = report.get("issues") if isinstance(report.get("issues"), list) else []
    normalized_issues = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity") or "MEDIUM").upper()
        if severity not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            severity = "MEDIUM"
        normalized_issues.append(
            {
                "type": issue.get("type") or "validation_issue",
                "severity": severity,
                "section": issue.get("section") or "TBD",
                "affected_requirement": issue.get("affected_requirement") or "TBD",
                "recommendation": issue.get("recommendation") or issue.get("detail") or "Review and refine this requirement.",
            }
        )
    is_valid = bool(report.get("is_valid")) and not any(issue["severity"] in {"CRITICAL", "HIGH"} for issue in normalized_issues)
    return {
        "is_valid": is_valid,
        "scores": normalized_scores,
        "issues": normalized_issues,
        "summary": report.get("summary") or "Validation completed.",
    }


def validate_documents_with_python(brd: str, frd: str) -> dict[str, Any]:
    brd_sections = parse_brd_sections(brd)
    fr_blocks = parse_functional_requirements(frd)
    issues: list[dict[str, str]] = []

    issues.extend(validate_mandatory_sections(brd_sections, frd, fr_blocks))
    issues.extend(validate_fr_numbering(fr_blocks))
    issues.extend(validate_duplicate_requirement_ids(fr_blocks))
    issues.extend(validate_traceability(fr_blocks, brd_sections))
    issues.extend(validate_missing_brd_mappings(brd_sections, fr_blocks))

    scores = score_python_validation(issues)
    return {
        "is_valid": not any(issue["severity"] in {"CRITICAL", "HIGH"} for issue in issues),
        "scores": scores,
        "issues": issues,
        "summary": f"Python structural validation found {len(issues)} issue(s).",
    }


def parse_brd_sections(brd: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current_key = ""
    current_lines: list[str] = []
    for line in brd.splitlines():
        heading = re.match(r"^(#{2,3})\s+(.+)$", line.strip())
        if heading:
            if current_key:
                sections[current_key] = "\n".join(current_lines).strip()
            title = heading.group(2).strip()
            section_match = re.match(r"(\d+(?:\.\d+)?)\.?\s*(.*)", title)
            current_key = section_match.group(1) if section_match else title
            sections[current_key] = ""
            current_lines = []
            continue
        if current_key:
            current_lines.append(line)
    if current_key:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


def parse_functional_requirements(frd: str) -> list[dict[str, Any]]:
    matches = list(re.finditer(r"(?m)^##\s+(FR-\d{3})\s*:\s*(.+)$", frd))
    blocks: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(frd)
        text = frd[start:end].strip()
        requirement_id_match = re.search(r"\*\*Requirement ID:\*\*\s*(FR-\d{3})", text)
        traceability_match = re.search(r"Maps to BRD Section:\s*([^\n]+)", text)
        blocks.append(
            {
                "id": match.group(1),
                "title": match.group(2).strip(),
                "requirement_id": requirement_id_match.group(1) if requirement_id_match else None,
                "traceability": traceability_match.group(1).strip() if traceability_match else "",
                "text": text,
            }
        )
    return blocks


def validate_mandatory_sections(
    brd_sections: dict[str, str],
    frd: str,
    fr_blocks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    required_brd_sections = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
    for section in required_brd_sections:
        if section not in brd_sections:
            issues.append(
                validation_issue(
                    "missing_mandatory_section",
                    "HIGH",
                    f"BRD Section {section}",
                    "Business Requirement Document",
                    f"Add mandatory BRD Section {section}.",
                )
            )
    if not re.search(r"(?m)^#\s+Functional Requirement Document", frd):
        issues.append(
            validation_issue(
                "missing_mandatory_section",
                "HIGH",
                "FRD Title",
                "Functional Requirement Document",
                "Add the Functional Requirement Document title section.",
            )
        )
    if not re.search(r"(?m)^##\s+FR-\d{3}", frd):
        issues.append(
            validation_issue(
                "missing_mandatory_section",
                "CRITICAL",
                "FRD Requirements",
                "Functional Requirements",
                "Add numbered functional requirements using FR-001, FR-002, etc.",
            )
        )
    mandatory_fr_labels = [
        "Requirement ID",
        "Title",
        "Description",
        "Priority",
        "Actors",
        "Preconditions",
        "Trigger",
        "Inputs",
        "Outputs",
        "Business Rules",
        "Main Workflow",
        "Alternative Workflow",
        "Exception Handling",
        "Dependencies",
        "Acceptance Criteria",
        "Traceability",
    ]
    for block in fr_blocks:
        for label in mandatory_fr_labels:
            if f"**{label}:**" not in block["text"]:
                issues.append(
                    validation_issue(
                        "missing_mandatory_section",
                        "MEDIUM",
                        block["id"],
                        block["title"],
                        f"Add mandatory FR section: {label}.",
                    )
                )
    return issues


def validate_fr_numbering(fr_blocks: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    ids = [block["id"] for block in fr_blocks]
    seen: set[str] = set()
    duplicate_ids = sorted({fr_id for fr_id in ids if fr_id in seen or seen.add(fr_id)})
    for fr_id in duplicate_ids:
        issues.append(
            validation_issue(
                "duplicate_fr_id",
                "HIGH",
                fr_id,
                fr_id,
                "Each functional requirement heading must use a unique FR ID.",
            )
        )
    numbers = sorted(int(fr_id.split("-")[1]) for fr_id in set(ids))
    if numbers:
        expected = list(range(1, max(numbers) + 1))
        missing = sorted(set(expected) - set(numbers))
        for number in missing:
            issues.append(
                validation_issue(
                    "missing_fr_id",
                    "MEDIUM",
                    f"FR-{number:03d}",
                    "Functional Requirement Numbering",
                    f"Add FR-{number:03d} or renumber requirements to remove the gap.",
                )
            )
        if numbers != expected:
            issues.append(
                validation_issue(
                    "numbering_consistency",
                    "MEDIUM",
                    "FRD Numbering",
                    "Functional Requirement Sequence",
                    "Ensure FR IDs are sequential with no gaps or duplicates.",
                )
            )
    return issues


def validate_duplicate_requirement_ids(fr_blocks: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    requirement_ids = [block["requirement_id"] for block in fr_blocks if block.get("requirement_id")]
    seen: set[str] = set()
    duplicates = sorted({req_id for req_id in requirement_ids if req_id in seen or seen.add(req_id)})
    for req_id in duplicates:
        issues.append(
            validation_issue(
                "duplicate_requirement_id",
                "HIGH",
                req_id,
                req_id,
                "Each Requirement ID field must be unique.",
            )
        )
    for block in fr_blocks:
        if block.get("requirement_id") and block["requirement_id"] != block["id"]:
            issues.append(
                validation_issue(
                    "numbering_consistency",
                    "MEDIUM",
                    block["id"],
                    block["title"],
                    f"Requirement ID field should match heading ID {block['id']}.",
                )
            )
    return issues


def validate_traceability(fr_blocks: list[dict[str, Any]], brd_sections: dict[str, str]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for block in fr_blocks:
        traceability = block.get("traceability", "")
        if not traceability:
            issues.append(
                validation_issue(
                    "traceability_gap",
                    "HIGH",
                    block["id"],
                    block["title"],
                    "Add Traceability with a specific BRD section and capability name.",
                )
            )
            continue
        section_match = re.search(r"(\d+(?:\.\d+)?)", traceability)
        if not section_match:
            issues.append(
                validation_issue(
                    "traceability_format",
                    "MEDIUM",
                    block["id"],
                    block["title"],
                    "Traceability must include a BRD section number.",
                )
            )
            continue
        section = section_match.group(1)
        if section not in brd_sections and section.split(".")[0] not in brd_sections:
            issues.append(
                validation_issue(
                    "brd_section_missing",
                    "HIGH",
                    block["id"],
                    traceability,
                    "Traceability references a BRD section that does not exist.",
                )
            )
        if re.search(r"\bIn Scope\b$", traceability, flags=re.IGNORECASE) or len(traceability.split("-")[-1].strip()) < 4:
            issues.append(
                validation_issue(
                    "traceability_format",
                    "LOW",
                    block["id"],
                    traceability,
                    "Traceability should include a specific capability name, not only a generic section label.",
                )
            )
    return issues


def validate_missing_brd_mappings(
    brd_sections: dict[str, str],
    fr_blocks: list[dict[str, Any]],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    in_scope = brd_sections.get("5.1", "")
    if not in_scope.strip():
        return issues
    in_scope_items = extract_bullet_items(in_scope)
    mapped_text = " ".join(
        f"{block.get('title', '')} {block.get('traceability', '')}" for block in fr_blocks
    ).lower()
    for item in in_scope_items:
        keywords = meaningful_words(item)
        if keywords and not any(keyword in mapped_text for keyword in keywords[:3]):
            issues.append(
                validation_issue(
                    "missing_mapping",
                    "MEDIUM",
                    "BRD Section 5.1",
                    item,
                    "Create or update a functional requirement that maps to this in-scope capability.",
                )
            )
    return issues


def extract_bullet_items(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def meaningful_words(text: str) -> list[str]:
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "user",
        "users",
        "system",
        "application",
        "platform",
        "feature",
        "capability",
    }
    return [
        word
        for word in re.findall(r"[a-zA-Z0-9]+", text.lower())
        if len(word) > 3 and word not in stop_words
    ]


def validation_issue(
    issue_type: str,
    severity: str,
    section: str,
    affected_requirement: str,
    recommendation: str,
) -> dict[str, str]:
    return {
        "type": issue_type,
        "severity": severity,
        "section": section,
        "affected_requirement": affected_requirement,
        "recommendation": recommendation,
    }


def score_python_validation(issues: list[dict[str, str]]) -> dict[str, int]:
    penalty_by_severity = {"CRITICAL": 35, "HIGH": 20, "MEDIUM": 10, "LOW": 3}
    total_penalty = sum(penalty_by_severity.get(issue["severity"], 10) for issue in issues)
    structural_score = max(0, 100 - total_penalty)
    traceability_penalty = sum(
        penalty_by_severity.get(issue["severity"], 10)
        for issue in issues
        if issue["type"] in {"traceability_gap", "traceability_format", "brd_section_missing", "missing_mapping"}
    )
    traceability_score = max(0, 100 - traceability_penalty)
    return {
        "overall_quality": structural_score,
        "requirement_mapping": traceability_score,
        "constraint_coverage": 100,
        "traceability": traceability_score,
        "consistency": structural_score,
    }


def merge_validation_reports(python_report: dict[str, Any], llm_report: dict[str, Any]) -> dict[str, Any]:
    python_scores = python_report.get("scores") or {}
    llm_scores = llm_report.get("scores") or {}
    merged_scores = {}
    for score_name in ["overall_quality", "requirement_mapping", "constraint_coverage", "traceability", "consistency"]:
        merged_scores[score_name] = min(
            normalize_score(python_scores.get(score_name), 100),
            normalize_score(llm_scores.get(score_name), 100),
        )
    issues = []
    issues.extend(python_report.get("issues") or [])
    issues.extend(llm_report.get("issues") or [])
    return {
        "is_valid": bool(python_report.get("is_valid")) and bool(llm_report.get("is_valid")),
        "scores": merged_scores,
        "issues": issues,
        "summary": "; ".join(
            summary
            for summary in [python_report.get("summary"), llm_report.get("summary")]
            if summary
        )
        or "Validation completed.",
    }


def classify_validation_severity(validation_result: dict[str, Any]) -> str:
    quality_score = validation_quality_score(validation_result)
    return "proceed" if quality_score >= 90 else "retry"


def max_refinement_iterations_for_validation(validation_result: dict[str, Any]) -> int:
    quality_score = validation_quality_score(validation_result)
    if quality_score >= 90:
        return 0
    if quality_score >= 70:
        return 1
    return 2


def should_export_with_notes(state: RequirementState) -> bool:
    validation_report = state.get("validation_report") or {}
    return bool(validation_report.get("issues"))


def validation_quality_score(validation_result: dict[str, Any]) -> int:
    return normalize_score(validation_result.get("scores", {}).get("overall_quality"), 0)


def normalize_score(value: Any, default: int) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = default
    return max(0, min(100, score))


def normalize_completeness_report(report: dict[str, Any], extracted_requirements: dict[str, Any]) -> dict[str, Any]:
    incomplete_fields = []
    complete_count = 0
    for field in REQUIRED_REQUIREMENT_FIELDS:
        requirement = extracted_requirements.get(field) or {}
        status = requirement.get("status")
        if status == "COMPLETE":
            complete_count += 1
            continue
        incomplete_fields.append(
            {
                "field": field,
                "reason": field_reason(field, status),
            }
        )

    overall_completion = round((complete_count / len(REQUIRED_REQUIREMENT_FIELDS)) * 100)
    reported_missing = report.get("missing_fields") if isinstance(report.get("missing_fields"), list) else []
    reason_by_field = {
        item.get("field"): item.get("reason")
        for item in reported_missing
        if isinstance(item, dict) and item.get("field") in REQUIRED_REQUIREMENT_FIELDS
    }
    for item in incomplete_fields:
        item["reason"] = reason_by_field.get(item["field"]) or item["reason"]

    return {
        "overall_completion": int(report.get("overall_completion", overall_completion)),
        "ready_for_generation": not incomplete_fields,
        "missing_fields": incomplete_fields,
    }


def normalize_clarifying_questions(
    questions: list[dict[str, Any]],
    missing_fields: list[dict[str, Any]],
) -> list[dict[str, str]]:
    allowed_fields = [item.get("field") for item in missing_fields if item.get("field") in REQUIRED_REQUIREMENT_FIELDS]
    question_by_field = {
        question.get("field"): question
        for question in questions
        if isinstance(question, dict) and question.get("field") in allowed_fields
    }
    normalized = []
    for field in allowed_fields:
        question = question_by_field.get(field) or {}
        normalized.append(
            {
                "id": f"Q{len(normalized) + 1}",
                "field": field,
                "question": question.get("question") or fallback_question_for_field(field),
                "category": question.get("category") or field,
            }
        )
    return normalized


def build_known_information(extracted_requirements: dict[str, Any]) -> dict[str, Any]:
    known: dict[str, Any] = {}
    for field in REQUIRED_REQUIREMENT_FIELDS:
        requirement = extracted_requirements.get(field) or {}
        value = requirement.get("value")
        if requirement.get("status") in {"COMPLETE", "PARTIAL"} and has_value(value):
            known[field] = value
    return known


def build_missing_information(
    extracted_requirements: dict[str, Any],
    missing_fields: list[dict[str, Any]],
) -> dict[str, str]:
    missing: dict[str, str] = {}
    for item in missing_fields:
        field = item.get("field")
        if field not in REQUIRED_REQUIREMENT_FIELDS:
            continue
        requirement = extracted_requirements.get(field) or {}
        missing[field] = requirement.get("status") or "MISSING"
    return missing


def has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def field_reason(field: str, status: str | None) -> str:
    label = field.replace("_", " ")
    if status == "PARTIAL":
        return f"{label.title()} is only partially described."
    return f"{label.title()} is missing."


def fallback_question_for_field(field: str) -> str:
    questions = {
        "business_objective": "What future business outcome should the new solution achieve beyond what is already described?",
        "current_process": "Are there any future-state workflow steps or process changes that the new solution must support beyond the process already described?",
        "pain_points": "What additional business problems should the new solution address that are not already described?",
        "stakeholders": "Are there any additional stakeholders not already mentioned, and what should they be able to do in the future system?",
        "functional_features": "What functional features should the application provide?",
        "user_workflows": "What future user workflows should the application support from start to finish?",
        "integrations": "What external systems should this application integrate with?",
        "constraints": "What timeline, budget, technical, compliance, or security constraints should be considered?",
        "success_metrics": "What measurable success metrics should determine whether this project worked?",
    }
    return questions[field]
