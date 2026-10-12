import pytest
from pathlib import Path
from docx import Document
import sys
import os

# Ensure tools and root are on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from tools.score_docs import score_documents, parse_input_markdown, stem_word, format_scoreboard


def test_stem_word():
    assert stem_word("notifications") == "notification"
    assert stem_word("reminders") == "reminder"
    assert stem_word("provisioning") == "provision"
    assert stem_word("workflows") == "workflow"


def test_parse_input_markdown(tmp_path):
    md_file = tmp_path / "sample_input.md"
    md_file.write_text("""
# Problem Statement
Our organization needs a system.

# Q1. What additional functional features do you envision?
* Automated checklist
* Document upload

# Q2. Desired user workflows
HR:
* Create onboarding request
IT:
* Provision laptop

# Q3. What external systems should this application integrate with?
* HRMS
* Slack

# Q4. Constraints
* Technology: Python backend
* Budget: Low cost

# Q5. Success Metrics
* Reduction in onboarding time
* High satisfaction score
""", encoding="utf-8")

    categories = parse_input_markdown(md_file.read_text(encoding="utf-8"))
    assert len(categories["features"]) == 2
    assert len(categories["workflow steps"]) == 2
    assert len(categories["integrations"]) == 2
    assert len(categories["constraints"]) == 2
    assert len(categories["metrics"]) == 2


def test_score_documents_with_seeded_docx(tmp_path):
    input_file = tmp_path / "test_input.md"
    input_file.write_text("""
# Problem Statement
We need an automated employee onboarding system.

# Q1. What additional functional features do you envision?
* Automated checklist and task assignment
* Document upload and verification

# Q2. Desired user workflows
HR:
* Create new employee onboarding request
IT:
* Provision laptop and email

# Q3. What external systems should this application integrate with?
* HRMS System
* Slack

# Q4. Constraints
* Technology: Python FastAPI
* Compliance: Data privacy

# Q5. Success Metrics
* Reduction in average onboarding time
* Task completion SLA
""", encoding="utf-8")

    # 1. BRD Document
    brd_doc = Document()
    brd_doc.core_properties.title = "Business Requirement Document"
    brd_doc.core_properties.subject = "We Spend Significant Time Onboarding"  # Insane title: leading stopword
    brd_doc.add_paragraph("Business Requirement Document")
    brd_doc.add_paragraph("IT must provision assets within 24 hours.")  # BRD timing: 24 hours
    brd_doc.add_paragraph("Automated reminders every 24 hours.")
    brd_doc.add_paragraph("Escalations triggered after 24 hours.")
    # Leaked banned phrase and validator leak in body
    brd_doc.add_paragraph("This shall be clarified in subsequent phases.")
    brd_doc.add_paragraph("[HIGH] Section 5.1: Missing requirement detail")
    brd_path = tmp_path / "BRD.docx"
    brd_doc.save(str(brd_path))

    # 2. FRD Document
    frd_doc = Document()
    frd_doc.core_properties.title = "Functional Requirement Document"
    frd_doc.core_properties.subject = "Smart Onboarding System"  # Sane title
    frd_doc.add_heading("FR-001: Automated Checklist and Task Assignment", level=1)
    frd_doc.add_paragraph("Requirement ID: FR-001")
    frd_doc.add_paragraph("Description: Automated checklist and task assignment for onboarding.")
    frd_doc.add_paragraph("IT shall provision laptop and email within 48 hours.")  # FRD timing: 48 hours -> CONFLICT with BRD
    frd_doc.add_paragraph("Traceability: Maps to BRD Section: 5.1")
    # Tags on non-requirement values:
    frd_doc.add_paragraph("Requirement ID: FR-001 [Assumption/Proposal: confirm]")
    frd_doc.add_paragraph("1 [Proposed default — confirm]. Step one starts.")
    # Untagged number with unit:
    frd_doc.add_paragraph("The maximum file size supported is 50 MB.")
    frd_path = tmp_path / "FRD.docx"
    frd_doc.save(str(frd_path))

    # 3. Epics Document
    epics_doc = Document()
    epics_doc.core_properties.title = "Epics & User Stories"
    epics_doc.core_properties.subject = "Smart Onboarding System"
    # Duplicate story ID US-001:
    epics_doc.add_heading("US-001: Create Request", level=2)
    epics_doc.add_paragraph("As an HR user I want to create request.")
    epics_doc.add_paragraph("Traceability: FR-001")

    epics_doc.add_heading("US-001: Duplicate Header", level=2)  # Duplicate!
    epics_doc.add_paragraph("As an admin I want to duplicate.")
    # Story without FR ID:
    epics_doc.add_heading("US-002: Provision Laptop", level=2)
    epics_doc.add_paragraph("As an IT engineer I want to provision laptop.")
    # Notice: no FR-xxx cited!

    epics_path = tmp_path / "Epics_Stories.docx"
    epics_doc.save(str(epics_path))

    # 4. Estimation Document
    est_doc = Document()
    est_doc.core_properties.title = "Project Estimation Report"
    est_doc.core_properties.subject = "Smart Onboarding System"
    # Reference dangling FR-999 and FR-100:
    t = est_doc.add_table(rows=2, cols=2)
    t.rows[0].cells[0].text = "Sprint 1"
    t.rows[0].cells[1].text = "FR-001"
    t.rows[1].cells[0].text = "Sprint 2"
    t.rows[1].cells[1].text = "FR-999 to FR-100"  # Dangling!
    est_path = tmp_path / "Project_Estimation.docx"
    est_doc.save(str(est_path))

    scores = score_documents(
        input_path=input_file,
        brd_path=brd_path,
        frd_path=frd_path,
        epics_path=epics_path,
        estimation_path=est_path,
    )

    # Validate computed metrics
    assert scores["duplicate_story_ids"] == 1  # US-001 repeated
    assert scores["stories_without_fr"] >= 1   # US-002 has no FR link
    assert scores["dangling_fr_count"] >= 1    # FR-999 / FR-100 not in FRD (only FR-001 defined)
    assert scores["untagged_numbers_with_units"] >= 1  # 50 MB is not in input and untagged
    assert scores["tags_on_non_requirement_values"] >= 2  # FR-001 [tag] and 1 [tag]
    assert scores["brd_frd_timing_conflicts"] >= 1  # Provisioning: 24 hours vs 48 hours
    assert scores["banned_phrases_count"] >= 2  # "shall be clarified" and "[HIGH]"
    assert scores["title_sanity_issues"] >= 1   # "We Spend Significant Time Onboarding" has stopword

    output_str = format_scoreboard(scores)
    assert "SDLC DOCUMENT GENERATION SCOREBOARD" in output_str


def test_known_bad_defects_seeded(tmp_path):
    """Verify detection of the 7 known defects described in Step A3 on synthetic seeded documents."""
    input_file = tmp_path / "test_input.md"
    input_file.write_text("""
# Problem Statement
Onboarding system.

# Q1. What additional functional features do you envision?
* Feature 1

# Q2. Desired user workflows
* Workflow 1

# Q3. What external systems should this application integrate with?
* System 1

# Q4. Constraints
* Constraint 1

# Q5. Success Metrics
* Metric 1
""", encoding="utf-8")

    # 1. BRD: Title 'Spend Significant Time And', reminder timing 24 hours, validator leak in Open Items
    brd_doc = Document()
    brd_doc.core_properties.title = "Spend Significant Time And"
    brd_doc.add_paragraph("Business Requirement Document")
    brd_doc.add_paragraph("Automated reminders after 24 hours.")
    # Validator leaks in Open Items
    brd_doc.add_heading("12. Open Items", level=2)
    brd_doc.add_paragraph("- Capability X is not covered by any User Story.")
    brd_doc.add_paragraph("- Integration Y lacks required technical element.")
    brd_path = tmp_path / "BRD.docx"
    brd_doc.save(str(brd_path))

    # 2. FRD: FR-001..FR-014, reminder timing 48 hours, 65 provenance tags on step numbers and FR IDs
    frd_doc = Document()
    frd_doc.core_properties.title = "Spend Significant Time And"
    for i in range(1, 15):
        fr_id = f"FR-{i:03d}"
        frd_doc.add_heading(f"{fr_id}: Feature {i}", level=2)
        frd_doc.add_paragraph(f"Requirement ID: {fr_id}")
        frd_doc.add_paragraph("Reminders sent 48 hours before the deadline.")
        frd_doc.add_paragraph("Traceability: Maps to BRD Section: 5.1")

    # Add 65 bad provenance tags on step numbers and FR IDs
    for s in range(1, 41):
        frd_doc.add_paragraph(f"Step {s} [Stated Fact — onboarding_case.md]: execute step")
    for s in range(1, 26):
        frd_doc.add_paragraph(f"FR-001 [Stated Fact]: requirement details for item {s}")

    frd_path = tmp_path / "FRD.docx"
    frd_doc.save(str(frd_path))

    # 3. Epics: US-001..US-005 repeated across 5 epics (18 stories total, all without FR IDs)
    epics_doc = Document()
    epics_doc.core_properties.title = "Spend Significant Time And"
    story_templates = [
        ("E-001", ["US-001", "US-002", "US-003", "US-004"]),
        ("E-002", ["US-001", "US-002", "US-003", "US-004"]),
        ("E-003", ["US-001", "US-002", "US-003", "US-004"]),
        ("E-004", ["US-001", "US-002", "US-003"]),
        ("E-005", ["US-001", "US-002", "US-003"]),
    ]
    total_seeded_stories = 0
    for epic_id, sids in story_templates:
        epics_doc.add_heading(f"{epic_id}: Epic Name", level=1)
        for sid in sids:
            total_seeded_stories += 1
            epics_doc.add_heading(f"{sid}: Story Title {total_seeded_stories}", level=2)
            epics_doc.add_paragraph(f"As a user I want story {total_seeded_stories} so that benefit.")
            # Note: No FR ID cited in any of the 18 stories!

    assert total_seeded_stories == 18
    epics_path = tmp_path / "Epics_Stories.docx"
    epics_doc.save(str(epics_path))

    # 4. Estimation: Cites FR-015..FR-018 (4 dangling FR references)
    est_doc = Document()
    est_doc.core_properties.title = "Spend Significant Time And"
    t = est_doc.add_table(rows=5, cols=2)
    t.rows[0].cells[0].text = "Sprint"
    t.rows[0].cells[1].text = "FRs Covered"
    t.rows[1].cells[0].text = "Sprint 1"
    t.rows[1].cells[1].text = "FR-015"
    t.rows[2].cells[0].text = "Sprint 2"
    t.rows[2].cells[1].text = "FR-016"
    t.rows[3].cells[0].text = "Sprint 3"
    t.rows[3].cells[1].text = "FR-017"
    t.rows[4].cells[0].text = "Sprint 4"
    t.rows[4].cells[1].text = "FR-018"
    est_path = tmp_path / "Project_Estimation.docx"
    est_doc.save(str(est_path))

    scores = score_documents(
        input_path=input_file,
        brd_path=brd_path,
        frd_path=frd_path,
        epics_path=epics_path,
        estimation_path=est_path,
    )

    # 1. Duplicate story IDs: US-001..US-005 repeated across 5 epics (18 stories total, 4 unique IDs -> 14 duplicates)
    assert scores["duplicate_story_ids"] == 14
    assert scores["total_stories_parsed"] == 18

    # 2. 4 dangling FR references: FR-015..FR-018 in Estimation not in FRD
    assert scores["dangling_fr_count"] == 4
    assert set(scores["dangling_frs"]) == {"FR-015", "FR-016", "FR-017", "FR-018"}

    # 3. 18 stories without an FR ID
    assert scores["stories_without_fr"] == 18

    # 4. Validator text inside BRD Open Items (2 items detected)
    assert scores["banned_phrases_count"] >= 2

    # 5. The title "Spend Significant Time And" (flagged on all 4 docs)
    assert scores["title_sanity_issues"] == 4

    # 6. BRD vs FRD conflict: reminders 24 hours vs 48 hours
    assert scores["brd_frd_timing_conflicts"] == 1

    # 7. Roughly 60 or more provenance tags on step numbers and FR IDs
    assert scores["tags_on_non_requirement_values"] >= 60


def test_a4_coverage_rows_and_metrics(tmp_path):
    """Verify A4 coverage reporting: Constraints and Metrics in BRD, Objectives vs Success Criteria."""
    input_file = tmp_path / "test_input.md"
    input_file.write_text("""
# Problem Statement
Test.

# Q1. What additional functional features do you envision?
* Feature Alpha

# Q2. Desired user workflows
* Workflow Beta

# Q3. What external systems should this application integrate with?
* Integration Gamma

# Q4. Constraints
* Azure Kubernetes Service

# Q5. Success Metrics
* Onboarding Time Reduction
* User Satisfaction Score
""", encoding="utf-8")

    # BRD with Project Objectives and Success Criteria
    brd_doc = Document()
    brd_doc.core_properties.title = "Smart Project"
    brd_doc.add_heading("Business Requirement Document", level=1)
    brd_doc.add_heading("3. Project Objectives", level=2)
    brd_doc.add_paragraph("Achieve Onboarding Time Reduction within 6 months.")
    # Notice: User Satisfaction Score is MISSING from Project Objectives!

    brd_doc.add_heading("8. Constraints", level=2)
    brd_doc.add_paragraph("Deployment target: Azure Kubernetes Service.")

    brd_doc.add_heading("11. Success Criteria", level=2)
    brd_doc.add_paragraph("- Onboarding Time Reduction: >= 50%")
    brd_doc.add_paragraph("- User Satisfaction Score: >= 90%")
    brd_path = tmp_path / "BRD.docx"
    brd_doc.save(str(brd_path))

    frd_doc = Document()
    frd_doc.core_properties.title = "Smart Project"
    frd_doc.add_heading("FR-001: Feature Alpha", level=2)
    frd_doc.add_paragraph("Requirement ID: FR-001")
    frd_doc.add_paragraph("Description: Feature Alpha and Workflow Beta with Integration Gamma.")
    frd_doc.add_paragraph("Traceability: Maps to BRD Section: 5.1")
    frd_path = tmp_path / "FRD.docx"
    frd_doc.save(str(frd_path))

    epics_doc = Document()
    epics_doc.core_properties.title = "Smart Project"
    epics_doc.add_heading("US-001: Feature Alpha Story", level=2)
    epics_doc.add_paragraph("As a user I want Feature Alpha and Workflow Beta with Integration Gamma.")
    epics_doc.add_paragraph("Traceability: FR-001")
    epics_path = tmp_path / "Epics_Stories.docx"
    epics_doc.save(str(epics_path))

    est_doc = Document()
    est_doc.core_properties.title = "Smart Project"
    est_doc.add_paragraph("Estimation")
    est_path = tmp_path / "Project_Estimation.docx"
    est_doc.save(str(est_path))

    scores = score_documents(
        input_path=input_file,
        brd_path=brd_path,
        frd_path=frd_path,
        epics_path=epics_path,
        estimation_path=est_path,
    )

    cov = scores["coverage_table"]
    # Features, Workflow Steps, Integrations have FR & Story covered
    assert cov["features"]["fr_covered"] == 1
    assert cov["features"]["story_covered"] == 1
    assert cov["features"]["brd_covered"] is None

    # Constraints has BRD covered
    assert cov["constraints"]["brd_covered"] == 1
    assert cov["constraints"]["fr_covered"] is None

    # Metrics: Only Onboarding Time Reduction is in BOTH Objectives & Success Criteria
    assert cov["metrics"]["brd_covered"] == 1
    assert cov["metrics"]["fr_covered"] is None

    # Missing metrics list should identify User Satisfaction Score missing from Project Objectives
    assert len(scores["missing_metrics_details"]) == 1
    assert "User Satisfaction Score" in scores["missing_metrics_details"][0]
    assert "Project Objectives" in scores["missing_metrics_details"][0]

