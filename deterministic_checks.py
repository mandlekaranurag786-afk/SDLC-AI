import re
from typing import Any
from arithmetic_utils import recompute_epics_arithmetic, recompute_estimation_cost

LEAKED_META_PHRASES = [
    (r"shall be clarified", "Leaked reviewer meta phrase 'shall be clarified'"),
    (r"must be defined", "Leaked reviewer meta phrase 'must be defined'"),
    (r"must be specified", "Leaked reviewer meta phrase 'must be specified'"),
    (r"this concludes", "Leaked meta statement 'This concludes...'"),
    (r"ensure that all items", "Leaked meta instructions 'ensure that all items'"),
]

def check_leaked_meta_phrases(doc_text: str, doc_name: str) -> list[dict[str, Any]]:
    issues = []
    if not doc_text:
        return issues

    for line_idx, line in enumerate(doc_text.splitlines(), start=1):
        stripped = line.strip()
        if "Appendix: Open Items" in stripped or "Open Items for Review" in stripped:
            continue
        for pattern, msg in LEAKED_META_PHRASES:
            if re.search(pattern, line, flags=re.IGNORECASE):
                issues.append({
                    "type": "leaked_meta_phrase",
                    "severity": "HIGH",
                    "section": doc_name,
                    "affected_requirement": f"Line {line_idx}",
                    "recommendation": f"{msg}: '{stripped[:60]}...'"
                })
                break
    return issues


def extract_numeric_facts(text: str) -> dict[str, list[str]]:
    """Extract numbers associated with key topics (days, hours, %, retention, thresholds)."""
    topic_patterns = {
        "it_provisioning": r"(\d+\s*(?:to|-)?\s*\d*\s*(?:days?|hours?))\s*(?:for|of)?\s*(?:it|provisioning|asset)",
        "reminder_frequency": r"(\d+\s*(?:hours?|days?))\s*(?:reminder|notification)",
        "escalation_sla": r"(\d+\s*(?:hours?|days?))\s*(?:escalation|sla)",
        "retention_period": r"(\d+\s*(?:years?|months?))\s*(?:retention|retain)",
    }
    extracted = {}
    if not text:
        return extracted

    for topic, pattern in topic_patterns.items():
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            extracted[topic] = list(dict.fromkeys(matches))
    return extracted


def check_numeric_conflicts(brd_text: str, frd_text: str) -> list[dict[str, Any]]:
    issues = []
    brd_facts = extract_numeric_facts(brd_text)
    frd_facts = extract_numeric_facts(frd_text)
    for topic, b_vals in brd_facts.items():
        if topic in frd_facts:
            f_vals = frd_facts[topic]
            if set(b_vals) != set(f_vals):
                issues.append({
                    "type": "numeric_conflict",
                    "severity": "HIGH",
                    "section": "BRD vs FRD Numeric Facts",
                    "affected_requirement": f"Topic: {topic}",
                    "recommendation": f"Numeric conflict between BRD ({b_vals}) and FRD ({f_vals}) for topic '{topic}'."
                })
    return issues


def check_numeric_timeline_consistency(
    epics_md: str,
    estimation_md: str,
    extracted_requirements: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """
    Scans Epics and Estimation documents for claims of sprints, weeks, or working days.
    Fails with HIGH severity if any claimed sprint count, total week count, or working days
    differs from the deterministically computed project timeline.
    Also checks if computed total_weeks exceeds any user constraint in extracted_requirements.
    """
    from arithmetic_utils import compute_project_timeline

    issues = []
    if not epics_md and not estimation_md:
        return issues

    # 1. Parse total story points from epics_md
    sp_match = re.search(r"\*\*Total Story Points:\*\*\s*(\d+)", epics_md)
    total_sp = int(sp_match.group(1)) if sp_match else 0

    if total_sp > 0:
        timeline = compute_project_timeline(total_sp)
        expected_sprints = timeline["sprints"]
        expected_weeks = timeline["total_weeks"]
        expected_days = timeline["fulltime_days"]

        # Check Epics sprint count claim
        epics_sprint_match = re.search(r"\*\*Estimated Sprints:\*\*\s*(\d+)", epics_md)
        if epics_sprint_match:
            claimed_sprints = int(epics_sprint_match.group(1))
            if claimed_sprints != expected_sprints:
                issues.append({
                    "type": "numeric_timeline_drift",
                    "severity": "HIGH",
                    "section": "Epics & User Stories",
                    "affected_requirement": "Backlog Summary Sprints",
                    "recommendation": f"Epics sprint claim ({claimed_sprints}) differs from computed value ({expected_sprints} sprints for {total_sp} story points)."
                })

        # Check Estimation document for sprint/week claims in headings/tables
        if estimation_md:
            # Check for conflicting "N sprints" or "N weeks" statements in text
            est_sprint_matches = re.findall(r"\b(\d+)\s+sprints?\b", estimation_md, re.IGNORECASE)
            for s_val in set(est_sprint_matches):
                if int(s_val) != expected_sprints:
                    issues.append({
                        "type": "numeric_timeline_drift",
                        "severity": "HIGH",
                        "section": "Estimation Report",
                        "affected_requirement": "Sprint Count",
                        "recommendation": f"Estimation mentions {s_val} sprints, which conflicts with computed {expected_sprints} sprints."
                    })

            # Check for conflicting total project weeks statements (e.g. "Estimated Project Duration: N weeks")
            est_week_matches = re.findall(r"duration[:\s]+(\d+)\s+weeks", estimation_md, re.IGNORECASE)
            for w_val in set(est_week_matches):
                if int(w_val) != expected_weeks:
                    issues.append({
                        "type": "numeric_timeline_drift",
                        "severity": "HIGH",
                        "section": "Estimation Report",
                        "affected_requirement": "Total Timeline Duration",
                        "recommendation": f"Estimation claims duration of {w_val} weeks, which conflicts with computed total of {expected_weeks} weeks."
                    })

    # 2. Check against user constraints if provided
    if extracted_requirements:
        constraints_str = str(extracted_requirements.get("constraints") or "")
        match_constraint_weeks = re.search(r"\b(\d+)\s*-\s*week\b|\b(\d+)\s+weeks?\b", constraints_str, re.IGNORECASE)
        if match_constraint_weeks:
            c_weeks = int(match_constraint_weeks.group(1) or match_constraint_weeks.group(2))
            if total_sp > 0:
                timeline = compute_project_timeline(total_sp)
                if timeline["total_weeks"] > c_weeks:
                    issues.append({
                        "type": "timeline_constraint_exceeded",
                        "severity": "HIGH",
                        "section": "Estimation Timeline vs Constraint",
                        "affected_requirement": "Timeline Constraint",
                        "recommendation": f"Computed duration ({timeline['total_weeks']} weeks) exceeds stated project constraint of {c_weeks} weeks."
                    })

    return issues


def check_sprint_count_mismatch(epics_text: str, estimation_text: str) -> list[dict[str, Any]]:
    issues = []
    if not epics_text or not estimation_text:
        return issues

    epics_sprint_match = re.search(r"(\d+)\s*(?:Sprints|sprints)", epics_text)
    est_sprint_match = re.search(r"(\d+)\s*(?:Sprints|sprints)", estimation_text)

    if epics_sprint_match and est_sprint_match:
        epics_sprints = int(epics_sprint_match.group(1))
        est_sprints = int(est_sprint_match.group(1))

        if epics_sprints != est_sprints:
            issues.append({
                "type": "sprint_mismatch",
                "severity": "HIGH",
                "section": "Epics vs Estimation",
                "affected_requirement": "Sprint Count Alignment",
                "recommendation": f"Sprint count mismatch: Epics document specifies {epics_sprints} sprints, but Estimation report specifies {est_sprints} sprints."
            })
    return issues


def check_story_fr_traceability(epics_text: str) -> list[dict[str, Any]]:
    issues = []
    if not epics_text:
        return issues

    story_blocks = re.findall(r"(US-\d+|User Story \d+[\s\S]*?)(?=(?:US-\d+|User Story \d+|$))", epics_text, flags=re.IGNORECASE)
    for block in story_blocks:
        story_id_match = re.search(r"(US-\d+|User Story \d+)", block, flags=re.IGNORECASE)
        story_id = story_id_match.group(1) if story_id_match else "User Story"
        if not re.search(r"\bFR-\d+\b", block, flags=re.IGNORECASE):
            issues.append({
                "type": "traceability_gap",
                "severity": "HIGH",
                "section": "Epics & User Stories",
                "affected_requirement": story_id,
                "recommendation": f"{story_id} does not cite a valid Functional Requirement ID (e.g. FR-1, FR-2)."
            })
    return issues


def check_fr_brd_traceability(frd_text: str) -> list[dict[str, Any]]:
    from feature_flags import ENABLE_VALIDATOR_FP_FIXES

    issues = []
    if not frd_text:
        return issues

    if ENABLE_VALIDATOR_FP_FIXES:
        raw_blocks = re.split(r"(?=(?:\n|^)##+\s*FR-\d+|(?:\n|^)FR-\d+[:\s])", frd_text)
        fr_blocks = [b for b in raw_blocks if re.search(r"FR-\d+", b)]
    else:
        fr_blocks = re.findall(r"(FR-\d+[\s\S]*?)(?=(?:FR-\d+|$))", frd_text, flags=re.IGNORECASE)

    for block in fr_blocks:
        fr_match = re.search(r"FR-\d+", block)
        fr_id = fr_match.group(0) if fr_match else "Functional Requirement"
        if ENABLE_VALIDATOR_FP_FIXES:
            has_trace = bool(re.search(r"(?:Maps to BRD Section|BRD Mapping|BRD Section|BR-\d+)\s*[:\s]*[\d.]+", block, flags=re.IGNORECASE))
        else:
            has_trace = bool(re.search(r"(?:BRD|BRD Section|BR-\d+)\s*[\d.]*", block, flags=re.IGNORECASE))

        if not has_trace:
            issues.append({
                "type": "traceability_gap",
                "severity": "HIGH",
                "section": "FRD",
                "affected_requirement": fr_id,
                "recommendation": f"{fr_id} does not cite a valid BRD Section item mapping."
            })
    return issues


def check_integration_technical_details(frd_text: str, extracted_requirements: dict[str, Any] | None = None, explicit_integrations: list[str] | None = None) -> list[dict[str, Any]]:
    """
    Checks that every required integration has a dedicated FR block in FRD,
    and that the FR block contains all 4 mandatory elements:
    1. Direction (inbound/outbound/both)
    2. Trigger
    3. Data Exchanged
    4. Failure Handling
    """
    from feature_flags import ENABLE_VALIDATOR_FP_FIXES

    issues = []
    if not frd_text:
        return issues

    integrations = list(explicit_integrations or [])
    if not integrations and extracted_requirements:
        raw_int = extracted_requirements.get("integrations") or {}
        if isinstance(raw_int, dict):
            val = raw_int.get("value") or raw_int.get("items") or []
            if isinstance(val, list):
                integrations = val
            elif isinstance(val, str):
                if ENABLE_VALIDATOR_FP_FIXES:
                    raw_items = re.split(r"[\n\r]+|(?:\s*,\s*)|(?:\s*;\s*)", val)
                    integrations = [re.sub(r"^[\s*\-•\d.]+", "", it).strip() for it in raw_items if re.sub(r"^[\s*\-•\d.]+", "", it).strip()]
                else:
                    integrations = [s.strip() for s in val.split(",") if s.strip()]
        elif isinstance(raw_int, list):
            integrations = raw_int

    if not integrations:
        default_systems = ["SAP SuccessFactors", "Active Directory", "DocuSign", "ServiceNow", "MS Teams", "Slack", "HRMS", "Outlook", "IAM", "SharePoint"]
        integrations = [s for s in default_systems if re.search(rf"\b{re.escape(s)}\b", frd_text, re.IGNORECASE)]

    # Parse FRD into FR blocks
    fr_blocks = re.split(r"(?=\n##\s+FR-\d+)", frd_text)

    # Required element patterns
    element_patterns = {
        "Direction": r"\b(direction|inbound|outbound|bi-directional|bidirectional|both)\b",
        "Trigger": r"\b(trigger|triggered|event|schedule|webhook|cron|api call)\b",
        "Data Exchanged": r"\b(data|payload|exchanged|schema|fields|sync|synchronized|master data|record|document)\b",
        "Failure Handling": r"\b(failure|fail|error|exception|retry|fallback|queue|circuit|backoff)\b"
    }

    for integration in set(integrations):
        int_clean = str(integration).strip()
        if not int_clean:
            continue

        # Find FR blocks that name this integration
        matching_frs = []
        for block in fr_blocks:
            if not block.strip().startswith("## FR-"):
                continue
            subparts = [p.strip() for p in re.split(r"[/,]", int_clean) if len(p.strip()) > 2]
            if re.search(rf"\b{re.escape(int_clean)}\b", block, re.IGNORECASE) or (ENABLE_VALIDATOR_FP_FIXES and any(re.search(rf"\b{re.escape(p)}\b", block, re.IGNORECASE) for p in subparts)):
                matching_frs.append(block)

        if not matching_frs:
            issues.append({
                "type": "missing_integration_fr",
                "severity": "HIGH",
                "section": "FRD System Integrations",
                "affected_requirement": int_clean,
                "recommendation": f"Missing dedicated Functional Requirement (FR-XXX) for integration '{int_clean}'. A mention in assumptions or BRD does not satisfy this requirement."
            })
            continue

        # Check technical elements across matching FR blocks
        combined_text = " ".join(matching_frs)
        missing_elements = []
        for elem_name, pattern in element_patterns.items():
            if not re.search(pattern, combined_text, re.IGNORECASE):
                missing_elements.append(elem_name)

        if missing_elements:
            issues.append({
                "type": "incomplete_integration_fr",
                "severity": "HIGH",
                "section": "FRD System Integrations",
                "affected_requirement": int_clean,
                "recommendation": f"FR for integration '{int_clean}' lacks required technical element(s): {', '.join(missing_elements)}. Each integration FR must specify Direction, Trigger, Data Exchanged, and Failure Handling."
            })

    return issues


def check_stakeholder_coverage(brd_text: str, frd_text: str, extracted_requirements: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from feature_flags import ENABLE_VALIDATOR_FP_FIXES

    issues = []
    if not brd_text or not frd_text:
        return issues

    roles = ["HR", "IT", "Reporting Manager", "Employee", "Delivery Heads"]
    if extracted_requirements:
        st_raw = extracted_requirements.get("stakeholders") or []
        if isinstance(st_raw, list) and st_raw:
            roles = [str(r) for r in st_raw]

    # Normalize delivery heads check
    if not any("delivery head" in r.lower() for r in roles):
        roles.append("Delivery Heads")

    for role in set(roles):
        r_clean = role.strip()
        if not r_clean:
            continue

        if ENABLE_VALIDATOR_FP_FIXES:
            base_r = re.sub(r"(?:s|es)$", "", r_clean, flags=re.IGNORECASE)
            role_pattern = rf"\b{re.escape(base_r)}(?:s|es)?\b"
        else:
            role_pattern = rf"\b{re.escape(r_clean)}\b"

        # Check BRD mention
        if not re.search(role_pattern, brd_text, re.IGNORECASE):
            issues.append({
                "type": "missing_stakeholder_coverage",
                "severity": "HIGH",
                "section": "BRD Section 4 Stakeholders",
                "affected_requirement": r_clean,
                "recommendation": f"Stakeholder role '{r_clean}' is missing from BRD Section 4 Stakeholders."
            })

        # Check FRD Actors mention
        if not re.search(role_pattern, frd_text, re.IGNORECASE):
            issues.append({
                "type": "missing_stakeholder_coverage",
                "severity": "HIGH",
                "section": "FRD Actors",
                "affected_requirement": r_clean,
                "recommendation": f"Stakeholder role '{r_clean}' is missing from FRD Actors fields."
            })

    return issues


def check_workflow_coverage(frd_text: str, epics_text: str, extracted_requirements: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    issues = []
    if not frd_text and not epics_text:
        return issues

    workflows = [
        "onboarding request", "upload employee details", "assign onboarding tasks",
        "track task completion", "onboarding dashboard", "send reminders",
        "provision laptop", "schedule introduction", "ask questions"
    ]

    for wf in workflows:
        if frd_text and not re.search(rf"\b{re.escape(wf)}\b", frd_text, re.IGNORECASE):
            issues.append({
                "type": "missing_workflow_coverage",
                "severity": "HIGH",
                "section": "FRD Workflows",
                "affected_requirement": wf,
                "recommendation": f"Workflow step '{wf}' is not covered by any Functional Requirement in the FRD."
            })
        if epics_text and not re.search(rf"\b{re.escape(wf)}\b", epics_text, re.IGNORECASE):
            issues.append({
                "type": "missing_workflow_coverage",
                "severity": "HIGH",
                "section": "Epics & User Stories",
                "affected_requirement": wf,
                "recommendation": f"Workflow step '{wf}' is not covered by any User Story in Epics."
            })

    return issues


def check_hr_dashboard_coverage(brd_text: str, frd_text: str) -> list[dict[str, Any]]:
    issues = []
    if not frd_text:
        return issues

    hr_dash_pattern = r"(?:Actors:[\s\S]*?\bHR\b[\s\S]*?Title:[\s\S]*?(?:dashboard|live view|real-time)|Title:[\s\S]*?(?:dashboard|live view|real-time)[\s\S]*?Actors:[\s\S]*?\bHR\b)"
    if not re.search(hr_dash_pattern, frd_text, re.IGNORECASE):
        issues.append({
            "type": "missing_hr_dashboard_coverage",
            "severity": "HIGH",
            "section": "FRD Functional Requirements",
            "affected_requirement": "HR Live Dashboard",
            "recommendation": "FRD must contain a dedicated Functional Requirement for HR (not only Manager) with a live dashboard/real-time tracking view."
        })
    return issues


def check_metrics_coverage(brd_text: str, extracted_requirements: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    issues = []
    if not brd_text:
        return issues

    metrics = [
        "onboarding time", "SLA", "manual", "provisioning", "automated",
        "pending tasks", "satisfaction", "escalation", "scheduled automatically", "completion rate"
    ]

    sec11_match = re.search(r"## 11\. Success Criteria.*?(?=##|\Z)", brd_text, re.DOTALL | re.IGNORECASE)
    sec11_text = sec11_match.group(0) if sec11_match else brd_text

    for m in metrics:
        if not re.search(rf"\b{re.escape(m)}\b", sec11_text, re.IGNORECASE):
            issues.append({
                "type": "missing_metric_coverage",
                "severity": "HIGH",
                "section": "BRD Section 11 Success Criteria",
                "affected_requirement": m,
                "recommendation": f"Success metric '{m}' from Q5 is missing from BRD Section 11 (Success Criteria)."
            })
    return issues


def check_constraints_coverage(brd_text: str, extracted_requirements: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    issues = []
    if not brd_text:
        return issues

    constraints = [
        "FastAPI", "Next.js", "SQL", "Role-based access", "data privacy", "APIs", "simultaneously", "infrastructure costs"
    ]

    sec8_match = re.search(r"## 8\. Constraints.*?(?=##|\Z)", brd_text, re.DOTALL | re.IGNORECASE)
    sec8_text = sec8_match.group(0) if sec8_match else brd_text

    for c in constraints:
        if not re.search(rf"\b{re.escape(c)}\b", sec8_text, re.IGNORECASE):
            issues.append({
                "type": "missing_constraint_coverage",
                "severity": "HIGH",
                "section": "BRD Section 8 Constraints",
                "affected_requirement": c,
                "recommendation": f"Constraint '{c}' from Q4 is missing from BRD Section 8 (Constraints)."
            })
    return issues


def run_deterministic_checks(state: dict[str, Any]) -> dict[str, Any]:
    """
    Executes full suite of deterministic document integrity checks:
    1. Leaked meta/reviewer phrases
    2. Same-topic BRD/FRD numeric conflicts
    3. Epics vs Estimation sprint mismatches
    4. Story -> FR ID traceability
    5. FR -> BRD Section traceability
    6. Integration technical detail enforcement
    7. Untagged numeric rule assumptions
    8. Stakeholder, Workflow, HR Dashboard, Metric, Constraint coverage checks
    Merges all findings into validation report.
    """
    from provenance_utils import check_untagged_numeric_rules, tag_numeric_provenance

    validation_report = state.get("validation_report") or {}
    existing_issues = list(validation_report.get("issues") or [])

    brd = state.get("brd_draft", "")
    frd = state.get("frd_draft", "")
    epics = state.get("epics_stories_draft", "")
    estimation = state.get("estimation_report", "")
    extracted_reqs = state.get("extracted_requirements") or {}
    problem_statement = state.get("problem_statement", "")

    # Auto-tag numeric rules if problem_statement is available
    if problem_statement:
        brd = tag_numeric_provenance(brd, problem_statement)
        frd = tag_numeric_provenance(frd, problem_statement)
        state["brd_draft"] = brd
        state["frd_draft"] = frd

    new_issues = []
    new_issues.extend(check_leaked_meta_phrases(brd, "BRD"))
    new_issues.extend(check_leaked_meta_phrases(frd, "FRD"))
    new_issues.extend(check_leaked_meta_phrases(epics, "Epics & Stories"))
    new_issues.extend(check_leaked_meta_phrases(estimation, "Estimation Report"))
    new_issues.extend(check_numeric_timeline_consistency(epics, estimation, extracted_reqs))
    new_issues.extend(check_story_fr_traceability(epics))
    new_issues.extend(check_fr_brd_traceability(frd))
    new_issues.extend(check_integration_technical_details(frd, extracted_reqs))
    new_issues.extend(check_stakeholder_coverage(brd, frd, extracted_reqs))
    new_issues.extend(check_workflow_coverage(frd, epics, extracted_reqs))
    new_issues.extend(check_hr_dashboard_coverage(brd, frd))
    new_issues.extend(check_metrics_coverage(brd, extracted_reqs))
    new_issues.extend(check_constraints_coverage(brd, extracted_reqs))
    new_issues.extend(check_untagged_numeric_rules(brd, problem_statement, "BRD"))
    new_issues.extend(check_untagged_numeric_rules(frd, problem_statement, "FRD"))

    # Deduplicate issues by recommendation
    seen = set()
    combined_issues = []
    for issue in existing_issues + new_issues:
        rec = issue.get("recommendation", "")
        if rec not in seen:
            seen.add(rec)
            combined_issues.append(issue)

    validation_report["issues"] = combined_issues
    state["validation_report"] = validation_report
    return validation_report
