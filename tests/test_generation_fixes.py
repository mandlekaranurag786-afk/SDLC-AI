"""
tests/test_generation_fixes.py

Unit tests for deterministic document generation improvements (Step B).
Tests:
- B.a: Story ID renumbering (US-001..US-0xx) across multiple epics & backlog summary table
- B.b: Story-to-FR link mapping (traceability injection, section and similarity mapping)
"""

import pytest
from traceability_utils import renumber_and_link_epics_stories, extract_frs_from_frd


def test_story_id_renumbering():
    epics_input = """# Epics and User Stories

## Epic 1: Onboarding Initiation
### US-001: Submit Onboarding Request
As an HR Specialist, I want to submit request.
Acceptance Criteria:
- Verify (US-001) is logged.

### US-002: Upload Documents
As an employee, I want to upload documents.

## Epic 2: IT Provisioning
### US-001: Provision Laptop
As an IT admin, I want to provision laptop.

### US-002: Create Email Account
As an IT admin, I want to create email.

### US-003: Configure VPN
As an IT admin, I want to configure VPN.

## Backlog Summary
| Epic | Story ID | Title | Points |
| --- | --- | --- | --- |
| Epic 1 | US-001 | Submit Onboarding Request | 3 |
| Epic 1 | US-002 | Upload Documents | 5 |
| Epic 2 | US-001 | Provision Laptop | 5 |
| Epic 2 | US-002 | Create Email Account | 3 |
| Epic 2 | US-003 | Configure VPN | 2 |
"""

    frd_input = """# Functional Requirements
## FR-001: Onboarding Request Submission
**Title:** Onboarding Request Submission
**Description:** System accepts HR onboarding submissions.
Maps to BRD Section: 5.1

## FR-002: Document Upload and Storage
**Title:** Document Upload and Storage
**Description:** Secure document upload for new hires.
Maps to BRD Section: 5.2

## FR-003: IT Asset and Access Provisioning
**Title:** IT Asset and Access Provisioning
**Description:** Provision laptops, emails, and VPN access.
Maps to BRD Section: 5.3
"""

    updated_md, findings = renumber_and_link_epics_stories(epics_input, frd_input)

    # 1. Verify global sequential numbering (US-001 to US-005)
    assert "### US-001: Submit Onboarding Request" in updated_md
    assert "### US-002: Upload Documents" in updated_md
    assert "### US-003: Provision Laptop" in updated_md
    assert "### US-004: Create Email Account" in updated_md
    assert "### US-005: Configure VPN" in updated_md

    # 2. Verify Backlog Summary table rows are sequentially renumbered
    assert "| US-001 | Submit Onboarding Request |" in updated_md
    assert "| US-002 | Upload Documents |" in updated_md
    assert "| US-003 | Provision Laptop |" in updated_md
    assert "| US-004 | Create Email Account |" in updated_md
    assert "| US-005 | Configure VPN |" in updated_md

    # 3. Verify Story-to-FR links injected
    assert "**Traceability:** FR-001" in updated_md
    assert "**Traceability:** FR-002" in updated_md
    assert "**Traceability:** FR-003" in updated_md


def test_estimation_fr_alignment():
    from arithmetic_utils import recompute_estimation_timeline

    estimation_input = """# Project Estimation
### 2.1 Sprint Breakdown
| Sprint | Duration | Focus Area | FRs Covered |
|--------|----------|------------|-------------|
| Sprint 1 | 2 weeks | Phase 1 | Old FR |

### 2.2 Phase Summary
- **Discovery & Setup:** 1 week

### 2.3 Total Timeline
**Estimated Project Duration:** 10 weeks
"""

    epics_input = "**Total Story Points:** 45"  # 3 sprints
    frd_input = "## FR-001: A\n## FR-002: B\n## FR-003: C\n## FR-004: D\n"

    result = recompute_estimation_timeline(estimation_input, epics_input, frd_md=frd_input)

    # Must contain FR-001 to FR-004
    assert "FR-001" in result
    assert "FR-004" in result
    # Must NOT hallucinate non-existent FRs like FR-005 .. FR-018
    assert "FR-005" not in result
    assert "FR-015" not in result
    assert "FR-018" not in result


def test_title_validation():
    from project_name_utils import clean_and_validate_project_name, resolve_project_name

    assert clean_and_validate_project_name("HR Employee Onboarding System") == "HR Employee Onboarding System"
    assert clean_and_validate_project_name("# Spend Significant Time And") is None
    assert clean_and_validate_project_name("SingleWord") is None
    assert clean_and_validate_project_name("One Two Three Four Five Six Seven Eight Nine") is None
    assert clean_and_validate_project_name("Untitled Project") is None
    assert clean_and_validate_project_name("Automated Onboarding Platform and") == "Automated Onboarding Platform"

    resolved = resolve_project_name(
        extracted_name="Automated Employee Onboarding Platform",
        problem_statement="HR teams spend significant time and effort coordinating onboarding.",
    )
    assert resolved == "Automated Employee Onboarding Platform"


def test_provenance_tag_filtering():
    from provenance_utils import tag_numeric_provenance

    doc_text = """# Business Requirements Document
1. Executive Summary
Step 1: Initiation of onboarding process
Requirement ID: FR-001
The system shall send automated reminders 24 hours prior to deadline.
IT team shall provision equipment within 48 hours.
"""

    user_input = "System shall send automated reminders 24 hours prior to deadline."
    tagged = tag_numeric_provenance(doc_text, user_input)

    # 1. Non-requirement tokens must NOT have tags
    assert "1. [" not in tagged
    assert "Step 1 [" not in tagged
    assert "FR-001 [" not in tagged

    # 2. Requirement facts from input must have Stated Fact tag
    assert "24 hours [Stated Fact: per user input]" in tagged

    # 3. Requirement numbers not in input must have Assumption/Proposal: confirm tag
    assert "48 hours [Assumption/Proposal: confirm]" in tagged


def test_validator_fp_fixes():
    from deterministic_checks import check_fr_brd_traceability, check_integration_technical_details, check_stakeholder_coverage
    from post_processor import scan_placeholders

    # 1. Maps to BRD Section recognition
    frd_text = """## FR-001: Sample
Requirement ID: FR-001
Title: Sample
Description: Test
Traceability: Maps to BRD Section: 5.1
"""
    assert len(check_fr_brd_traceability(frd_text)) == 0

    # 2. Multiline/bulleted integrations list
    extracted_reqs = {
        "integrations": {
            "value": "* HRMS / Employee Management System\n* Microsoft Outlook / Google Calendar\n* Email / Microsoft Teams / Slack"
        }
    }
    frd_with_ints = """## FR-011: HRMS Integration
HRMS integration details.
Direction: bi-directional
Trigger: API call
Data Exchanged: employee master data sync
Failure Handling: retry queue with backoff

## FR-012: Calendar Integration
Outlook and Google Calendar.
Direction: outbound
Trigger: schedule
Data Exchanged: calendar invites
Failure Handling: log error

## FR-013: Messaging Integration
Slack and Teams notifications.
Direction: outbound
Trigger: webhook event
Data Exchanged: notification payload
Failure Handling: retry on failure
"""
    issues = check_integration_technical_details(frd_with_ints, extracted_requirements=extracted_reqs)
    assert len(issues) == 0

    # 3. Singular vs Plural role matching
    brd_roles = "4. Stakeholders: Delivery Head and Employees."
    frd_roles = "Actors: Delivery Heads, Employee."
    st_issues = check_stakeholder_coverage(brd_roles, frd_roles)
    # Both "Delivery Heads" and "Employee" should be satisfied
    unmatched = [i["affected_requirement"] for i in st_issues]
    assert "Delivery Heads" not in unmatched
    assert "Employee" not in unmatched

    # 4. Intentional Target: TBD under Objectives & Success Criteria
    doc_tbd = """## 3. Project Objectives
- Average onboarding time: Target: TBD
- Completion rate: Target: to be defined

## 5. Scope
- User authentication: TBD
"""
    ph_issues = scan_placeholders(doc_tbd)
    # Line 2 and 3 allowed, line 6 flagged
    assert len(ph_issues) == 1
    assert "Line 6" in ph_issues[0]["affected_requirement"]


def test_brd_open_items_clean_leaks():
    from brd_hygiene_utils import clean_validator_leaks_from_open_items

    dirty_brd = """# Business Requirement Document
## 11. Success Criteria
Metrics here.

## 12. Open Items
- Timeline for project completion is not finalized.
- Budget for the project is pending approval.
- Stakeholder roles 'Delivery Heads' and 'Reporting Manager' need to be added to BRD Section 4 Stakeholders.
- Success metrics 'escalation', 'scheduled automatically', and 'completion rate' need to be added to BRD Section 11 Success Criteria.
- Constraints 'FastAPI', 'Next.js', 'SQL' need to be added to BRD Section 8 Constraints.

## Appendix: Open Items for Review
Validator findings.
"""
    cleaned = clean_validator_leaks_from_open_items(dirty_brd)
    assert "Timeline for project completion is not finalized." in cleaned
    assert "Budget for the project is pending approval." in cleaned
    assert "need to be added to BRD Section" not in cleaned


def test_q5_metrics_alignment():
    from brd_hygiene_utils import ensure_q5_metrics_aligned

    incomplete_brd = """# Business Requirement Document
## 3. Project Objectives
- Reduce onboarding time by 50%
- SLA compliance above 90%

## 11. Success Criteria
- Satisfaction score above 85%
"""
    aligned = ensure_q5_metrics_aligned(incomplete_brd)

    # All 10 metrics must now be present in both sections
    for metric in [
        "onboarding time", "SLA", "manual", "provisioning", "automated",
        "pending tasks", "satisfaction", "escalation", "scheduled automatically", "completion rate"
    ]:
        obj_sec = aligned.split("## 11. Success Criteria")[0]
        sc_sec = aligned.split("## 11. Success Criteria")[1]
        assert metric.lower() in obj_sec.lower(), f"Missing {metric} in Objectives"
        assert metric.lower() in sc_sec.lower(), f"Missing {metric} in Success Criteria"




