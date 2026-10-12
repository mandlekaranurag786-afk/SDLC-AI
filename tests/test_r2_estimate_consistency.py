import pytest
from currency_utils import detect_budget, synchronize_estimation_currency
from arithmetic_utils import recompute_estimation_cost

def test_detect_budget_eur():
    budget, curr = detect_budget("Our total budget is 50,000 EUR for this project.")
    assert budget == 50000.0
    assert curr == "EUR"

def test_detect_budget_gbp():
    budget, curr = detect_budget("Budget allocation is £40,000 for the MVP.")
    assert budget == 40000.0
    assert curr == "GBP"

def test_estimation_currency_conversion_inr():
    est_md = """# Project Estimation Report
### 4.1 Effort Breakdown
| Role | Count | Days | Offshore Rate (USD) | Onshore Rate (USD) |
| Tech Lead | 1 | 20 | 50 - 60 | 120 - 150 |

### 4.2 Total Cost Range
| Scenario | Estimated Cost (USD) |
|----------|---------------|
| Offshore Team | $1,000 - $1,200 |
"""
    updated = recompute_estimation_cost(est_md, target_currency="INR")
    assert "Estimated Cost (INR)" in updated
    assert "₹" in updated or "INR" in updated

def test_synchronize_estimation_currency():
    est_md = """# Project Estimation Report
| Scenario | Estimated Cost (USD) |
| Offshore Team | $10,000 |
"""
    synced = synchronize_estimation_currency(est_md, "EUR")
    assert "Estimated Cost (EUR)" in synced
    assert "1 USD =" in synced
