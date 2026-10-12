import pytest
from deterministic_checks import (
    check_leaked_meta_phrases,
    check_numeric_conflicts,
    check_sprint_count_mismatch,
    check_story_fr_traceability,
    check_fr_brd_traceability,
    run_deterministic_checks
)

def test_leaked_meta_phrases_detected():
    brd = """# Business Requirements
The exact retention period shall be clarified by compliance team.
This concludes the initial business scope.
"""
    issues = check_leaked_meta_phrases(brd, "BRD")
    assert len(issues) == 2
    assert any("shall be clarified" in issue["recommendation"] for issue in issues)
    assert any("This concludes" in issue["recommendation"] for issue in issues)


def test_numeric_conflict_detected():
    brd = "The IT provisioning process takes 3 to 5 days for IT asset assignment."
    frd = "System must trigger 1 to 2 days for IT provisioning upon candidate sign-off."
    
    issues = check_numeric_conflicts(brd, frd)
    assert len(issues) >= 1
    assert issues[0]["type"] == "numeric_conflict"
    assert "it_provisioning" in issues[0]["affected_requirement"].lower()


def test_sprint_count_mismatch_detected():
    epics = """# Epics & Stories
### Epic 1: Onboarding Portal
Total Story Points: 40 points
Estimated Velocity: 20 points per sprint (2 Sprints)
"""
    estimation = """# Project Estimation Report
## Sprint Breakdown & Timeline
Total Sprints: 5 Sprints (10 Weeks)
Total Cost: $50,000 USD
"""
    issues = check_sprint_count_mismatch(epics, estimation)
    assert len(issues) == 1
    assert issues[0]["type"] == "sprint_mismatch"
    assert "5 sprints" in issues[0]["recommendation"]


def test_story_fr_traceability_gap():
    epics = """# Epics & User Stories
### User Story 1: Candidate Sign-in
As a candidate, I want to sign in so that I can see my tasks.
Acceptance Criteria: Sign in with OTP.
"""
    issues = check_story_fr_traceability(epics)
    assert len(issues) == 1
    assert issues[0]["type"] == "traceability_gap"
    assert "US-1" in issues[0]["affected_requirement"] or "User Story" in issues[0]["affected_requirement"]


def test_fr_brd_traceability_gap():
    frd = """# Functional Requirements
### FR-1: Automated Email Dispatch
The system shall send emails to HR upon candidate completion.
"""
    issues = check_fr_brd_traceability(frd)
    assert len(issues) == 1
    assert issues[0]["type"] == "traceability_gap"
    assert "FR-1" in issues[0]["affected_requirement"]


def test_run_deterministic_checks_full_state():
    state = {
        "brd_draft": "The IT provisioning takes 3 to 5 days for IT asset assignment. Scope shall be clarified.",
        "frd_draft": "FR-1: System sends email. IT provisioning takes 1 to 2 days for IT asset.",
        "epics_stories_draft": "US-1: User logs in.",
        "estimation_report": "Total Sprints: 5 Sprints",
        "validation_report": {"issues": []}
    }
    report = run_deterministic_checks(state)
    issues = report.get("issues", [])
    assert len(issues) >= 3
    types = {i["type"] for i in issues}
    assert "leaked_meta_phrase" in types
    assert "traceability_gap" in types
