import pytest
from currency_utils import detect_budget, convert_from_usd, format_currency, check_budget_risk
from arithmetic_utils import recompute_estimation_cost

def test_detect_budget():
    amt, curr = detect_budget("Project budget constraint: INR 25 lakhs with 4 month timeline")
    assert curr == "INR"
    assert amt == 2_500_000.0

    amt2, curr2 = detect_budget("Max budget is $50,000 USD")
    assert curr2 == "USD"
    assert amt2 == 50_000.0

    amt3, curr3 = detect_budget("Budget 1.5 Crores INR")
    assert curr3 == "INR"
    assert amt3 == 15_000_000.0


def test_budget_risk_warning_trigger():
    # 25 lakhs INR budget = 2,500,000 INR
    budget_inr = 2_500_000.0
    min_cost_inr = 3_910_000.0  # 46,000 USD * 85.0

    has_risk, msg = check_budget_risk(min_cost_inr, budget_inr, "INR")
    assert has_risk is True
    assert "Budget Risk Warning" in msg
    assert "exceeds the stated budget constraint" in msg


def test_recompute_estimation_cost_with_inr_budget():
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
"""

    processed = recompute_estimation_cost(
        raw_estimation_md,
        target_currency="INR",
        user_budget=2_500_000.0
    )

    # Offshore low: $46,000 * 85 = ₹3,910,000 (INR 3.91 Lakhs / 3,910,000)
    assert "INR" in processed
    assert "Exchange rate assumption: 1 USD = 85.00 INR" in processed
    assert "Budget Risk Warning" in processed
    assert "3,910,000" in processed
