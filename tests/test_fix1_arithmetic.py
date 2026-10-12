import pytest
from arithmetic_utils import recompute_epics_arithmetic, recompute_estimation_cost

def test_recompute_epics_arithmetic():
    raw_epics_md = """# Epics & User Stories

## Summary Table
| Epic ID | Epic Name | Stories Count | Total Story Points |
|---------|-----------|---------------|-------------------|
| E-001 | Onboarding | 99 | 999 |

---

## E-001: Onboarding Workflows

### US-001: Associate Profile Creation
**User Story:** As an admin...
**Priority:** High
**Story Points:** 5

### US-002: Document Upload
**User Story:** As an associate...
**Priority:** Medium
**Story Points:** 8

## E-002: Notification Engine

### US-003: Email Alerts
**User Story:** As a system...
**Priority:** Low
**Story Points:** 3

## Backlog Summary
| Story ID | Story Title | Epic | Priority | Story Points |
|----------|------------|------|----------|-------------|
| US-001 | Profile | E-001 | High | 5 |

**Total Story Points:** 999
**Estimated Sprints:** 99
"""

    processed = recompute_epics_arithmetic(raw_epics_md, velocity_per_sprint=10)

    # US-001 (5) + US-002 (8) = 13 points for E-001 (2 stories)
    # US-003 (3) = 3 points for E-002 (1 story)
    # Total backlog points = 16 points. Velocity = 10 -> ceil(16/10) = 2 sprints.
    assert "| E-001 | Onboarding Workflows | 2 | 13 |" in processed
    assert "| E-002 | Notification Engine | 1 | 3 |" in processed
    assert "**Total Story Points:** 16" in processed
    assert "**Estimated Sprints:** 2" in processed


def test_recompute_estimation_cost():
    raw_estimation_md = """# Project Estimation Report

### 4.1 Effort Breakdown
| Role | Count | Working Days | Day Rate (Offshore) | Day Rate (Onshore) |
|------|-------|-------------|--------------------|--------------------|
| Senior Backend Developer | 1 | 40 | $900-$1,200 | $1,800-$2,500 |
| QA Engineer | 1 | 20 | $500-$700 | $1,000-$1,400 |

### 4.2 Total Cost Range
| Scenario | Estimated Cost |
|----------|---------------|
| Offshore Team | $XX,XXX - $XX,XXX |
| Onshore Team | $XX,XXX - $XX,XXX |
| Blended (50/50) | $XX,XXX - $XX,XXX |
"""

    processed = recompute_estimation_cost(raw_estimation_md)

    # Offshore low: 1*40*900 + 1*20*500 = 36,000 + 10,000 = $46,000
    # Offshore high: 1*40*1200 + 1*20*700 = 48,000 + 14,000 = $62,000
    # Onshore low: 1*40*1800 + 1*20*1000 = 72,000 + 20,000 = $92,000
    # Onshore high: 1*40*2500 + 1*20*1400 = 100,000 + 28,000 = $128,000
    # Blended low: (46000 + 92000) / 2 = $69,000
    # Blended high: (62000 + 128000) / 2 = $95,000

    assert "| Offshore Team | $46,000 USD - $62,000 USD |" in processed
    assert "| Onshore Team | $92,000 USD - $128,000 USD |" in processed
    assert "| Blended (50/50) | $69,000 USD - $95,000 USD |" in processed


def test_recompute_estimation_placeholder_rejection():
    raw_estimation_with_placeholder = """# Project Estimation Report

### 4.1 Effort Breakdown
| Role | Count | Working Days | Day Rate (Offshore) | Day Rate (Onshore) |
|------|-------|-------------|--------------------|--------------------|

### 4.2 Total Cost Range
| Scenario | Estimated Cost |
|----------|---------------|
| Offshore Team | $XX,XXX - TBD |
"""
    with pytest.raises(ValueError, match="Estimation report contains unresolved cost placeholders"):
        recompute_estimation_cost(raw_estimation_with_placeholder)
