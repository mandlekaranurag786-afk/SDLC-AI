import pytest
from post_processor import strip_chatty_closings
from deterministic_checks import check_leaked_meta_phrases

def test_strip_chatty_closings():
    doc_text = """# Business Requirement Document

## 1. Executive Summary
This is a clean document.

This concludes the BRD document generation. End of document."""

    cleaned = strip_chatty_closings(doc_text)
    assert "This concludes" not in cleaned
    assert "End of document" not in cleaned
    assert "Executive Summary" in cleaned


def test_check_leaked_meta_phrases():
    doc_text = """# Functional Requirement Document

## FR-001: IT Provisioning
**Description:** The exact SLA shall be clarified by IT team.
**Business Rules:** Note: ensure that all items are verified.
"""

    issues = check_leaked_meta_phrases(doc_text, "FRD")
    assert len(issues) >= 1
    types = [i["type"] for i in issues]
    assert "leaked_meta_phrase" in types
