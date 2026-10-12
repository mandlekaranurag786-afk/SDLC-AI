import pytest
from provenance_utils import tag_numeric_provenance, check_untagged_numeric_rules

def test_tag_numeric_provenance_fact_vs_assumption():
    user_input = "We need 3 to 5 days for IT provisioning."
    doc_text = """# Business Requirements
The IT asset allocation requires 3 to 5 days.
The system SLA target is 99.9% availability.
"""
    tagged = tag_numeric_provenance(doc_text, user_input)
    assert "[Stated Fact: per user input]" in tagged
    assert "[Assumption/Proposal: confirm]" in tagged

def test_check_untagged_numeric_rules():
    user_input = "We need 3 to 5 days for IT provisioning."
    doc_text = """# Business Requirements
The system SLA target is 99.9% availability.
"""
    issues = check_untagged_numeric_rules(doc_text, user_input, "BRD")
    assert len(issues) >= 1
    assert issues[0]["type"] == "untagged_numeric_assumption"
