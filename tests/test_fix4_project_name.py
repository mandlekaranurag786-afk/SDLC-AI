import pytest
from project_name_utils import resolve_project_name, clean_and_validate_project_name

def test_stopword_rejection():
    # "We are a mid-size enterprise..." must NOT produce "Are Mid-Size Enterprise"
    problem = "We are a mid-size enterprise looking for automated onboarding."
    name = resolve_project_name(problem_statement=problem)
    assert not name.startswith("Are ")
    assert not name.startswith("We ")
    assert name != "Are Mid-Size Enterprise"
    assert "automated onboarding" in name.lower() or "mid-size enterprise" in name.lower() or name == "Untitled Project"


def test_user_provided_name_precedence():
    problem = "We are a mid-size enterprise looking for automated onboarding."
    user_name = "Global HR Onboarding Suite"
    extracted_name = "Automated Onboarding Tool"

    resolved = resolve_project_name(
        user_provided_name=user_name,
        extracted_name=extracted_name,
        problem_statement=problem
    )
    assert resolved == "Global HR Onboarding Suite"


def test_extracted_name_precedence_over_fallback():
    problem = "We are a mid-size enterprise looking for automated onboarding."
    extracted_name = "Enterprise Employee Onboarding Portal"

    resolved = resolve_project_name(
        user_provided_name=None,
        extracted_name=extracted_name,
        problem_statement=problem
    )
    assert resolved == "Enterprise Employee Onboarding Portal"


def test_fallback_untitled_project():
    problem = "We are the a an our"
    resolved = resolve_project_name(problem_statement=problem)
    assert resolved == "Untitled Project"
