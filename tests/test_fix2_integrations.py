import pytest
from integration_utils import check_items_coverage, extract_structured_list

def test_extract_structured_list():
    raw_input = "SAP SuccessFactors (core HRMS), MS Active Directory (SSO/identity), MS Teams, DocuSign, ServiceNow, HRMS, Email workflow, Slack"
    extracted = extract_structured_list(raw_input)
    assert len(extracted) == 8
    assert "SAP SuccessFactors (core HRMS)" in extracted or "SAP SuccessFactors" in extracted[0]
    assert "Slack" in extracted


def test_check_items_coverage_all_present():
    items = [
        "SAP SuccessFactors",
        "MS Active Directory",
        "MS Teams",
        "DocuSign",
        "ServiceNow",
        "HRMS",
        "Email workflow",
        "Slack"
    ]

    sample_doc = """
    # Section 5.1 In Scope
    - Integration with SAP Success Factors for core HR employee data sync
    - Integration with Azure AD for SSO and identity management
    - Integration with Microsoft Teams bot for notifications
    - Integration with DocuSign for e-signature of offer letters
    - Integration with ServiceNow for IT asset ticket creation
    - Integration with internal HRMS platform
    - Automated email workflow for manager approvals
    - Slack support channel for employee queries
    """

    present, missing = check_items_coverage(sample_doc, items)
    assert len(missing) == 0
    assert len(present) == 8


def test_check_items_coverage_missing_detected():
    items = [
        "SAP SuccessFactors",
        "MS Active Directory",
        "MS Teams",
        "DocuSign",
        "ServiceNow",
        "HRMS",
        "Email workflow",
        "Slack"
    ]

    sample_doc = """
    # Section 5.1 In Scope
    - Integration with SAP Success Factors
    - Integration with Azure AD
    - Integration with ServiceNow
    """

    present, missing = check_items_coverage(sample_doc, items)
    assert "MS Teams" in missing
    assert "DocuSign" in missing
    assert "Slack" in missing
    assert len(missing) == 5
    assert len(present) == 3
