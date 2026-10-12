import pytest
from arithmetic_utils import compute_project_timeline, recompute_estimation_timeline
from deterministic_checks import check_numeric_timeline_consistency

def test_compute_project_timeline():
    # 45 story points / 15 velocity = 3 sprints
    # 1 setup + 3*2 sprints + 2 QA + 1 UAT = 10 weeks
    # 10 weeks * 5 days = 50 working days
    res = compute_project_timeline(45)
    assert res["sprints"] == 3
    assert res["sprint_weeks"] == 6
    assert res["total_weeks"] == 10
    assert res["fulltime_days"] == 50


def test_recompute_estimation_timeline_writeback():
    epics_md = """# Epics & User Stories
## Summary Table
| Epic ID | Epic Name | Stories Count | Total Story Points |
|---------|-----------|---------------|-------------------|
| E-001 | Core Features | 6 | 45 |

**Total Story Points:** 45
**Estimated Sprints:** 3
"""
    estimation_md = """# Project Estimation Report

### 2.1 Sprint Breakdown
| Sprint | Duration | Focus Area | FRs Covered |
|--------|----------|------------|-------------|
| Sprint 1 | 2 weeks | Old Area | FR-001 |

### 2.2 Phase Summary
Old phase summary text

### 2.3 Total Timeline
Old timeline text

## 4. Cost Estimate
### 4.1 Effort Breakdown
| Role | Count | Working Days | Day Rate (Offshore) | Day Rate (Onshore) |
|------|-------|-------------|--------------------|--------------------|
| Senior Backend Developer | 1 | 999 | $900-$1,200 | $1,800-$2,500 |
| QA Engineer (part-time) | 1 | 999 | $400-$700 | $800-$1,200 |

## 4.2 Total Cost Range
| Scenario | Estimated Cost |
"""
    updated_est = recompute_estimation_timeline(estimation_md, epics_md)

    assert "Sprint 3" in updated_est
    assert "10 weeks" in updated_est
    assert "50 working days" in updated_est
    # Senior Backend Developer (fulltime) -> 50 working days
    # QA Engineer (part-time) -> 25 working days
    assert "| Senior Backend Developer | 1 | 50 |" in updated_est
    assert "| QA Engineer (part-time) | 1 | 25 |" in updated_est


def test_check_numeric_timeline_consistency_drift():
    epics_md = "**Total Story Points:** 45\n**Estimated Sprints:** 3"
    # Claiming 9 sprints and 25 weeks in estimation when computed is 3 sprints / 10 weeks
    estimation_md = "Estimation report mentions 9 sprints and duration: 25 weeks."

    issues = check_numeric_timeline_consistency(epics_md, estimation_md)
    assert len(issues) >= 1
    types = [i["type"] for i in issues]
    assert "numeric_timeline_drift" in types


def test_check_numeric_timeline_consistency_exceeds_constraint():
    epics_md = "**Total Story Points:** 90\n**Estimated Sprints:** 6"
    # 90 SP = 6 sprints = 1 + 12 + 2 + 1 = 16 weeks
    estimation_md = "Estimated Project Duration: 16 weeks."
    constraints = {"constraints": "Must deliver MVP within 8 weeks."}

    issues = check_numeric_timeline_consistency(epics_md, estimation_md, extracted_requirements=constraints)
    types = [i["type"] for i in issues]
    assert "timeline_constraint_exceeded" in types
