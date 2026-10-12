import pytest
from deterministic_checks import check_integration_technical_details

def test_high_level_integration_flagged():
    frd = """# Functional Requirements
## FR-1: Active Directory User Sync
The system integrates with Active Directory for employee authentication.
"""
    extracted = {"integrations": ["Active Directory"]}
    issues = check_integration_technical_details(frd, extracted)
    assert len(issues) == 1
    assert issues[0]["type"] == "incomplete_integration_fr"
    assert issues[0]["severity"] == "HIGH"
    assert "Active Directory" in issues[0]["affected_requirement"]


def test_technical_spec_integration_passes():
    frd = """# Functional Requirements
## FR-1: Active Directory User Sync
**Direction:** Inbound and Outbound.
**Trigger:** Triggered on user creation.
**Data Exchanged:** JSON payload containing user data.
**Failure Handling:** Exponential backoff retry on failure.
"""
    extracted = {"integrations": ["Active Directory"]}
    issues = check_integration_technical_details(frd, extracted)
    assert len(issues) == 0
