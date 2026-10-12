"""
brd_hygiene_utils.py

Deterministic utilities for:
- Fix B.g: Isolating validator reports from BRD Open Items & cleaning leaked validator lines
- Fix B.h: Aligning all 10 Q5 metrics under Project Objectives and Success Criteria
"""

import re
from typing import Any
from feature_flags import ENABLE_ISOLATE_VALIDATOR_OPEN_ITEMS, ENABLE_METRIC_ALIGNMENT

Q5_METRICS = [
    ("onboarding time", "Average onboarding time: Target: to be defined"),
    ("SLA", "Tasks completed within SLA: Target: to be defined"),
    ("manual", "Reduction in manual HR/IT effort: Target: to be defined"),
    ("provisioning", "Asset and access provisioning turnaround: Target: to be defined"),
    ("automated", "Percentage of onboarding tasks automated: Target: to be defined"),
    ("pending tasks", "Number of overdue or pending tasks: Target: to be defined"),
    ("satisfaction", "Employee onboarding satisfaction score: Target: to be defined"),
    ("escalation", "Number of onboarding issues and escalation / escalations: Target: to be defined"),
    ("scheduled automatically", "Percentage of meetings scheduled automatically: Target: to be defined"),
    ("completion rate", "Overall onboarding task completion rate: Target: to be defined"),
]

LEAKED_VALIDATOR_PATTERNS = [
    re.compile(r"\[(HIGH|CRITICAL|MEDIUM|LOW)\]", re.IGNORECASE),
    re.compile(r"need to be added to BRD Section", re.IGNORECASE),
    re.compile(r"is missing from BRD Section", re.IGNORECASE),
    re.compile(r"does not cite a valid BRD", re.IGNORECASE),
    re.compile(r"flagged during automated validation", re.IGNORECASE),
    re.compile(r"not covered by any User Story", re.IGNORECASE),
    re.compile(r"lacks required technical element", re.IGNORECASE),
    re.compile(r"Missing dedicated Functional Requirement", re.IGNORECASE),
    re.compile(r"Stakeholder role '.*?' is missing", re.IGNORECASE),
    re.compile(r"Success metric '.*?' from Q5 is missing", re.IGNORECASE),
    re.compile(r"Constraint '.*?' from Q4 is missing", re.IGNORECASE),
]


def clean_validator_leaks_from_open_items(brd_text: str) -> str:
    """
    Prevents automated validator reports and recommendation strings from leaking
    into the BRD body Section 12 (Open Items).
    """
    if not brd_text or not ENABLE_ISOLATE_VALIDATOR_OPEN_ITEMS:
        return brd_text

    # Match Open Items section before Appendix or end of doc
    match = re.search(r"(##+\s*(?:\d+[\.\)]\s*)?Open Items[^\n]*\n)([\s\S]*?)(?=\n##|\Z)", brd_text, re.IGNORECASE)
    if not match:
        return brd_text

    header = match.group(1)
    body = match.group(2)

    cleaned_lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_leak = any(pat.search(line) for pat in LEAKED_VALIDATOR_PATTERNS)
        if not is_leak:
            cleaned_lines.append(line)

    if not cleaned_lines:
        cleaned_lines = [
            "- Timeline for full organizational rollout pending final departmental schedule sign-off.",
            "- Production API credentials for third-party systems to be verified during deployment phase.",
        ]

    new_section = header + "\n".join(cleaned_lines) + "\n"
    start_pos, end_pos = match.span()
    return brd_text[:start_pos] + new_section + brd_text[end_pos:]


def ensure_q5_metrics_aligned(brd_text: str) -> str:
    """
    Ensures all 10 Q5 metrics appear under both 'Project Objectives' and 'Success Criteria'
    (headings identified by text, not section numbers).
    Appends any missing metric with 'Target: to be defined'.
    """
    if not brd_text or not ENABLE_METRIC_ALIGNMENT:
        return brd_text

    modified_text = brd_text

    # 1. Align Project Objectives
    obj_match = re.search(r"(##+\s*(?:\d+[\.\)]\s*)?Project Objectives[^\n]*\n)([\s\S]*?)(?=\n##|\Z)", modified_text, re.IGNORECASE)
    if obj_match:
        header = obj_match.group(1)
        body = obj_match.group(2)
        missing_appends = []
        for term, template in Q5_METRICS:
            if not re.search(rf"\b{re.escape(term)}\b", body, re.IGNORECASE):
                missing_appends.append(f"- {template}")

        if missing_appends:
            new_body = body.rstrip() + "\n" + "\n".join(missing_appends) + "\n"
            start_pos, end_pos = obj_match.span()
            modified_text = modified_text[:start_pos] + header + new_body + modified_text[end_pos:]

    # 2. Align Success Criteria
    sc_match = re.search(r"(##+\s*(?:\d+[\.\)]\s*)?Success Criteria[^\n]*\n)([\s\S]*?)(?=\n##|\Z)", modified_text, re.IGNORECASE)
    if sc_match:
        header = sc_match.group(1)
        body = sc_match.group(2)
        missing_appends = []
        for term, template in Q5_METRICS:
            if not re.search(rf"\b{re.escape(term)}\b", body, re.IGNORECASE):
                missing_appends.append(f"- {template}")

        if missing_appends:
            new_body = body.rstrip() + "\n" + "\n".join(missing_appends) + "\n"
            start_pos, end_pos = sc_match.span()
            modified_text = modified_text[:start_pos] + header + new_body + modified_text[end_pos:]

    return modified_text
