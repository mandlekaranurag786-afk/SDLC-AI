import os
import pytest
from provenance_utils import tag_numeric_provenance, check_untagged_numeric_rules

def test_provenance_with_real_no_target_input():
    with open("/home/anurag-mandlekar/.gemini/antigravity/scratch/qa/test_inputs/onboarding_case.md") as f:
        real_input = f.read()

    doc_text = """## 11. Success Criteria
- Reduction in onboarding time: 70%
- Asset provisioning SLA: within 4 hours
"""
    tagged = tag_numeric_provenance(doc_text, real_input)

    # In real_input, there are no target values (no 70% or 4 hours in input)
    assert "[Proposed default — confirm]" in tagged or "[Assumption/Proposal: confirm]" in tagged
    assert "[Stated Fact: per user input]" not in tagged


def test_provenance_with_detailed_target_input():
    with open("/home/anurag-mandlekar/.gemini/antigravity/scratch/qa/test_inputs/detailed_case_with_targets.md") as f:
        detailed_input = f.read()

    doc_text = """## 11. Success Criteria
- Asset provisioning SLA: within 4 hours
- IT provisioning delay: 3 to 5 days
"""
    tagged = tag_numeric_provenance(doc_text, detailed_input)

    # In detailed_input, "4 hours" and "3 to 5 days" ARE present
    assert "[Stated Fact: per user input]" in tagged


def test_check_untagged_numeric_rules():
    real_input = "We need an onboarding system for remote staff."
    doc_text = "The system must process requests within 72 hours."

    issues = check_untagged_numeric_rules(doc_text, real_input, "BRD")
    assert len(issues) == 1
    assert "72hours" in issues[0]["recommendation"].lower() or "72" in issues[0]["recommendation"]
