import pytest
from deterministic_checks import check_integration_technical_details

def test_integration_missing_fr():
    frd_text = """# Functional Requirement Document

## FR-001: User Authentication
**Description:** System authenticates users.
"""
    integrations = ["DocuSign", "ServiceNow"]
    issues = check_integration_technical_details(frd_text, explicit_integrations=integrations)
    
    assert len(issues) == 2
    types = [i["type"] for i in issues]
    assert "missing_integration_fr" in types
    affected = [i["affected_requirement"] for i in issues]
    assert "DocuSign" in affected
    assert "ServiceNow" in affected


def test_integration_name_only_mention():
    frd_text = """# Functional Requirement Document

## FR-001: Document Management
**Description:** Mentions DocuSign for e-signature.
**Assumptions:** DocuSign account exists.

## FR-002: ServiceNow Ticketing
**Title:** ServiceNow Integration
**Description:** Creates tickets in ServiceNow.
**Direction:** Outbound
**Trigger:** IT ticket creation event
**Data Exchanged:** User ID, Asset Name, Priority
**Failure Handling:** Retry 3 times then log to queue
"""
    integrations = ["DocuSign", "ServiceNow"]
    issues = check_integration_technical_details(frd_text, explicit_integrations=integrations)
    
    # DocuSign is only mentioned at high-level inside FR-001, missing 4 technical elements
    # ServiceNow has all 4 elements and should pass without findings
    assert len(issues) == 1
    assert issues[0]["affected_requirement"] == "DocuSign"
    assert issues[0]["type"] == "incomplete_integration_fr"
    assert "Direction" in issues[0]["recommendation"] or "Trigger" in issues[0]["recommendation"]


def test_integration_full_technical_details_pass():
    frd_text = """# Functional Requirement Document

## FR-001: DocuSign E-Signature Sync
**Title:** DocuSign Integration
**Description:** Synchronizes offer letters with DocuSign.
**Direction:** Bi-directional
**Trigger:** Onboarder offer letter generation event
**Data Exchanged:** Employee Name, Email, Offer PDF Payload
**Failure Handling:** Webhook retry policy with 5-min backoff
"""
    integrations = ["DocuSign"]
    issues = check_integration_technical_details(frd_text, explicit_integrations=integrations)
    assert len(issues) == 0
