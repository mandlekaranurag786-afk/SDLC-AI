import pytest
from deterministic_checks import (
    check_stakeholder_coverage,
    check_workflow_coverage,
    check_hr_dashboard_coverage,
    check_metrics_coverage,
    check_constraints_coverage
)

def test_check_stakeholder_coverage_missing_delivery_heads():
    brd = "## 4. Stakeholders\n- HR Team\n- IT Department\n- Reporting Managers\n- Employees"
    frd = "**Actors:** HR, IT, Manager, Employee"

    issues = check_stakeholder_coverage(brd, frd)
    assert len(issues) >= 1
    reqs = [i["affected_requirement"] for i in issues]
    assert "Delivery Heads" in reqs


def test_check_workflow_coverage_missing():
    frd = "## FR-001: Create Onboarding Request\n**Actors:** HR"
    epics = "### US-001: Create Onboarding Request\n**Story Points:** 5"

    issues = check_workflow_coverage(frd, epics)
    assert len(issues) >= 1
    reqs = [i["affected_requirement"] for i in issues]
    assert "provision laptop" in reqs or "schedule introduction" in reqs


def test_check_hr_dashboard_coverage_missing():
    brd = "HR dashboard"
    # Only Manager has dashboard, HR missing
    frd = "## FR-005: Manager Dashboard\n**Title:** Manager Live Dashboard\n**Actors:** Reporting Manager"

    issues = check_hr_dashboard_coverage(brd, frd)
    assert len(issues) == 1
    assert issues[0]["type"] == "missing_hr_dashboard_coverage"


def test_check_metrics_coverage_missing():
    brd = "## 11. Success Criteria\n- Reduction in onboarding time"

    issues = check_metrics_coverage(brd)
    assert len(issues) >= 1
    reqs = [i["affected_requirement"] for i in issues]
    assert "SLA" in reqs or "provisioning" in reqs


def test_check_constraints_coverage_missing():
    brd = "## 8. Constraints\n- FastAPI backend\n- Next.js frontend"

    issues = check_constraints_coverage(brd)
    assert len(issues) >= 1
    reqs = [i["affected_requirement"] for i in issues]
    assert "SQL" in reqs or "Role-based access" in reqs
