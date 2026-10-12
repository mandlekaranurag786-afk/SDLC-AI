#!/usr/bin/env python3
"""
tools/score_docs.py

Scoreboard tool for SDLC generated documents.
Takes four generated DOCX files (BRD, FRD, Epics & Stories, Estimation)
and an input markdown file (e.g. qa/test_inputs/onboarding_case.md),
and computes a table of code-verified counts:
  (a) Input items found per category vs covered by FR vs covered by Story
  (b) Duplicate story IDs
  (c) Stories without an FR ID
  (d) FR IDs referenced anywhere that do not exist in the FRD
  (e) Numbers with units in documents not in input and untagged
  (f) Tags on non-requirement values (step numbers, IDs, section numbers)
  (g) BRD vs FRD conflicts for reminder, escalation, provisioning timing
  (h) Banned phrases & validator text inside body sections
  (i) Title sanity issues
"""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

from docx import Document


STOPWORDS = {
    "we", "are", "the", "a", "an", "our", "organizations", "organization",
    "company", "i", "you", "they", "my", "is", "need", "want", "require",
    "build", "create", "develop", "spend", "significant"
}

BANNED_PHRASES = [
    r"shall be clarified",
    r"must be defined",
    r"must be specified",
    r"this concludes",
]

NUMBER_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(days?|hours?|hrs?|sprints?|weeks?|months?|years?|%|percent|mb|gb|tb|seconds?|mins?|minutes?|lakhs?|crores?|k)\b",
    re.IGNORECASE,
)


def stem_word(w: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]", "", w).lower()
    if clean.endswith("ies") and len(clean) > 4:
        return clean[:-3] + "y"
    if clean.endswith("ses") and len(clean) > 4:
        return clean[:-2]
    if clean.endswith("s") and not clean.endswith("ss") and len(clean) > 3:
        return clean[:-1]
    if clean.endswith("ing") and len(clean) > 5:
        return clean[:-3]
    if clean.endswith("ed") and len(clean) > 4:
        return clean[:-2]
    return clean


def extract_docx_content(docx_path: str | Path) -> dict[str, Any]:
    """Extract paragraphs, tables, full text, and separate body vs appendix text."""
    doc = Document(str(docx_path))
    full_lines: list[str] = []
    body_lines: list[str] = []
    appendix_lines: list[str] = []
    in_appendix = False

    # Extract title from core properties and first heading/paragraph
    prop_title = (doc.core_properties.title or "").strip()
    prop_subject = (doc.core_properties.subject or "").strip()

    paragraphs_text: list[str] = []
    for p in doc.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        if p.style and p.style.name and p.style.name.lower().startswith("heading") and not txt.startswith("#"):
            level_match = re.search(r"\d+", p.style.name)
            level = int(level_match.group(0)) if level_match else 2
            txt = f"{'#' * min(level, 4)} {txt}"

        paragraphs_text.append(txt)
        if "appendix:" in txt.lower() or ("appendix" in txt.lower() and "open items" in txt.lower()):
            in_appendix = True

        full_lines.append(txt)
        if in_appendix:
            appendix_lines.append(txt)
        else:
            body_lines.append(txt)

    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells]
            row_text = " | ".join(row_cells)
            full_lines.append(row_text)
            if in_appendix:
                appendix_lines.append(row_text)
            else:
                body_lines.append(row_text)

    # Document project title heuristics
    doc_title = prop_subject or prop_title
    if not doc_title and paragraphs_text:
        doc_title = paragraphs_text[0]

    return {
        "title": doc_title,
        "full_text": "\n".join(full_lines),
        "body_text": "\n".join(body_lines),
        "appendix_text": "\n".join(appendix_lines),
        "lines": full_lines,
        "body_lines": body_lines,
    }


def parse_input_markdown(md_content: str) -> dict[str, list[str]]:
    """Parse categories from onboarding_case.md: features, workflows, integrations, constraints, metrics."""
    categories: dict[str, list[str]] = {
        "features": [],
        "workflow steps": [],
        "integrations": [],
        "constraints": [],
        "metrics": [],
    }

    current_cat = None
    lines = md_content.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if re.search(r"Q1\..*functional features", stripped, re.IGNORECASE):
            current_cat = "features"
            continue
        elif re.search(r"Q2\..*user workflows", stripped, re.IGNORECASE):
            current_cat = "workflow steps"
            continue
        elif re.search(r"Q3\..*external systems.*integrate", stripped, re.IGNORECASE):
            current_cat = "integrations"
            continue
        elif re.search(r"Q4\..*constraints", stripped, re.IGNORECASE):
            current_cat = "constraints"
            continue
        elif re.search(r"Q5\..*success metrics", stripped, re.IGNORECASE):
            current_cat = "metrics"
            continue
        elif stripped.startswith("#"):
            current_cat = None
            continue

        if current_cat and stripped.startswith("*"):
            item_text = stripped.lstrip("* ").strip()
            # Clean off leading category prefixes like 'Technology: '
            clean_item = re.sub(r"^[A-Za-z]+:\s*", "", item_text)
            if clean_item:
                categories[current_cat].append(clean_item)

    return categories


def item_matches_text(item: str, text: str) -> bool:
    """Singular/plural and stemming tolerant check if an item concept appears in text."""
    # Split into keywords, ignore short filler words
    raw_words = re.findall(r"[A-Za-z0-9]+", item)
    content_words = [w for w in raw_words if len(w) > 2 and w.lower() not in STOPWORDS]
    if not content_words:
        return False

    stemmed_targets = [stem_word(w) for w in content_words]
    text_words = [stem_word(w) for w in re.findall(r"[A-Za-z0-9]+", text)]
    text_stems_set = set(text_words)

    matched = sum(1 for st in stemmed_targets if st in text_stems_set)
    # Require at least 60% match or direct substring match
    if matched / len(stemmed_targets) >= 0.6:
        return True
    if len(item) > 5 and item.lower() in text.lower():
        return True
    return False


def extract_section_content_by_keyword(text: str, keyword: str) -> str:
    """Extract section text under a heading containing keyword up to next heading of same or higher level."""
    lines = text.splitlines()
    in_section = False
    section_lines: list[str] = []
    kw_lower = keyword.lower()
    for line in lines:
        stripped = line.strip()
        # Check if line is a heading for this keyword
        is_heading = (
            stripped.startswith("#")
            or re.match(r"^\d+(?:\.\d+)?\.?\s+[A-Z]", stripped)
        ) and kw_lower in stripped.lower()

        if is_heading:
            in_section = True
            continue
        elif in_section:
            # End of section reached if next major heading encountered
            if re.match(r"^#{1,2}\s+", stripped) or re.match(r"^\d+\.\s+[A-Z]", stripped):
                break
            section_lines.append(line)
    return "\n".join(section_lines).strip()


def score_documents(
    input_path: str | Path,
    brd_path: str | Path,
    frd_path: str | Path,
    epics_path: str | Path,
    estimation_path: str | Path,
) -> dict[str, Any]:
    input_text = Path(input_path).read_text(encoding="utf-8")
    categories = parse_input_markdown(input_text)

    brd_data = extract_docx_content(brd_path)
    frd_data = extract_docx_content(frd_path)
    epics_data = extract_docx_content(epics_path)
    est_data = extract_docx_content(est_path := estimation_path)

    doc_hashes = {
        "BRD": hashlib.sha256(Path(brd_path).read_bytes()).hexdigest(),
        "FRD": hashlib.sha256(Path(frd_path).read_bytes()).hexdigest(),
        "Epics": hashlib.sha256(Path(epics_path).read_bytes()).hexdigest(),
        "Estimation": hashlib.sha256(Path(est_path).read_bytes()).hexdigest(),
    }

    # Parse individual FR blocks from FRD
    fr_blocks = re.split(r"(?=(?:FR-\d+|##\s+FR-\d+))", frd_data["full_text"])

    # Parse individual Story blocks from Epics (Heading-based for accurate story definition)
    story_matches = list(
        re.finditer(
            r"(?m)^(?:#{2,3}\s*)?(?:User Story\s+)?(US-\d+)\s*:\s*(.+)$",
            epics_data["full_text"],
            re.IGNORECASE,
        )
    )
    parsed_stories: list[dict[str, Any]] = []
    if story_matches:
        for idx, match in enumerate(story_matches):
            start = match.start()
            end = story_matches[idx + 1].start() if idx + 1 < len(story_matches) else len(epics_data["full_text"])
            block_text = epics_data["full_text"][start:end].strip()
            backlog_m = re.search(r"(?m)^#{1,2}\s+Backlog Summary", block_text, re.IGNORECASE)
            if backlog_m:
                block_text = block_text[:backlog_m.start()].strip()
            sid = match.group(1).upper()
            title = match.group(2).strip()
            has_fr = bool(re.search(r"\bFR-\d+\b", block_text, re.IGNORECASE))
            parsed_stories.append({
                "id": sid,
                "title": title,
                "text": block_text,
                "has_fr": has_fr,
            })
    else:
        raw_blocks = re.split(r"(?m)(?=^(?:#{2,3}\s*)?US-\d+\b)", epics_data["full_text"])
        for b in raw_blocks:
            m = re.search(r"\b(US-\d+)\b", b)
            if m and ("User Story" in b or "As a" in b or "Priority" in b):
                has_fr = bool(re.search(r"\bFR-\d+\b", b, re.IGNORECASE))
                parsed_stories.append({
                    "id": m.group(1).upper(),
                    "title": "",
                    "text": b,
                    "has_fr": has_fr,
                })

    total_stories_parsed = len(parsed_stories)
    stories_without_fr = sum(1 for s in parsed_stories if not s["has_fr"])

    # Section extracts for BRD coverage checks
    obj_text = (
        extract_section_content_by_keyword(brd_data["full_text"], "Project Objectives")
        or extract_section_content_by_keyword(brd_data["full_text"], "Objective")
    )
    crit_text = (
        extract_section_content_by_keyword(brd_data["full_text"], "Success Criteria")
        or extract_section_content_by_keyword(brd_data["full_text"], "Success")
    )
    constraints_text = (
        extract_section_content_by_keyword(brd_data["full_text"], "Constraint")
        or brd_data["full_text"]
    )

    # (a) Input items found vs covered by FR / Story (Features, Workflows, Integrations)
    # vs covered by BRD (Constraints, Metrics)
    coverage_table: dict[str, dict[str, Any]] = {}
    total_input = 0
    total_fr = 0
    total_story = 0
    total_brd = 0
    missing_metrics_details: list[str] = []

    for cat, items in categories.items():
        if cat in ["features", "workflow steps", "integrations"]:
            fr_cov = 0
            story_cov = 0
            for item in items:
                if any(item_matches_text(item, block) for block in fr_blocks) or item_matches_text(item, frd_data["full_text"]):
                    fr_cov += 1
                if any(item_matches_text(item, s["text"]) for s in parsed_stories) or item_matches_text(item, epics_data["full_text"]):
                    story_cov += 1

            coverage_table[cat] = {
                "input_count": len(items),
                "fr_covered": fr_cov,
                "story_covered": story_cov,
                "brd_covered": None,
            }
            total_input += len(items)
            total_fr += fr_cov
            total_story += story_cov

        elif cat == "constraints":
            brd_cov = 0
            for item in items:
                if item_matches_text(item, constraints_text) or item_matches_text(item, brd_data["full_text"]):
                    brd_cov += 1
            coverage_table[cat] = {
                "input_count": len(items),
                "fr_covered": None,
                "story_covered": None,
                "brd_covered": brd_cov,
            }
            total_input += len(items)
            total_brd += brd_cov

        elif cat == "metrics":
            brd_cov = 0
            for item in items:
                in_obj = item_matches_text(item, obj_text)
                in_crit = item_matches_text(item, crit_text)
                if in_obj and in_crit:
                    brd_cov += 1
                else:
                    miss_locs = []
                    if not in_obj:
                        miss_locs.append("Project Objectives")
                    if not in_crit:
                        miss_locs.append("Success Criteria")
                    missing_metrics_details.append(f"{item} (missing in: {', '.join(miss_locs)})")

            coverage_table[cat] = {
                "input_count": len(items),
                "fr_covered": None,
                "story_covered": None,
                "brd_covered": brd_cov,
            }
            total_input += len(items)
            total_brd += brd_cov

    coverage_table["Total"] = {
        "input_count": total_input,
        "fr_covered": total_fr,
        "story_covered": total_story,
        "brd_covered": total_brd,
    }

    # (b) Duplicate story IDs in Epics doc
    heading_story_ids = [s["id"] for s in parsed_stories]
    heading_counts: dict[str, int] = {}
    for sid in heading_story_ids:
        heading_counts[sid] = heading_counts.get(sid, 0) + 1
    duplicate_story_ids = sum(count - 1 for count in heading_counts.values() if count > 1)

    # (d) FR IDs referenced anywhere that do not exist in the FRD
    defined_frs = set()
    for m in re.finditer(r"(?:##\s+)?(FR-\d+)\s*:", frd_data["full_text"], re.IGNORECASE):
        defined_frs.add(m.group(1).upper())
    for m in re.finditer(r"Requirement ID:\s*(FR-\d+)", frd_data["full_text"], re.IGNORECASE):
        defined_frs.add(m.group(1).upper())

    all_docs_text = "\n".join([
        brd_data["full_text"],
        frd_data["full_text"],
        epics_data["full_text"],
        est_data["full_text"],
    ])

    dangling_frs = set()
    range_matches = re.finditer(r"\b(FR-(\d+))\s+to\s+(FR-(\d+))\b", all_docs_text, re.IGNORECASE)
    for rm in range_matches:
        start_num = int(rm.group(2))
        end_num = int(rm.group(4))
        for num in range(start_num, end_num + 1):
            cand = f"FR-{num:03d}"
            if cand not in defined_frs:
                dangling_frs.add(cand)

    for fr_ref in re.findall(r"\bFR-\d+\b", all_docs_text, re.IGNORECASE):
        norm_ref = fr_ref.upper()
        if norm_ref not in defined_frs:
            dangling_frs.add(norm_ref)

    dangling_fr_count = len(dangling_frs)

    # (e) Numbers with units in documents not in input and untagged
    input_num_units = set()
    for m in NUMBER_UNIT_PATTERN.finditer(input_text):
        input_num_units.add((m.group(1), m.group(2).lower()))
    input_bare_nums = set(re.findall(r"\d+(?:\.\d+)?", input_text))

    untagged_count = 0
    all_lines = brd_data["lines"] + frd_data["lines"] + epics_data["lines"] + est_data["lines"]
    for line in all_lines:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#") or "|" in line_clean:
            continue
        if "Version:" in line_clean or "Generated Date:" in line_clean or "Page " in line_clean:
            continue

        for m in NUMBER_UNIT_PATTERN.finditer(line_clean):
            num = m.group(1)
            unit = m.group(2).lower()
            if (num, unit) not in input_num_units and num not in input_bare_nums:
                has_tag = bool(re.search(r"\[(?:Stated Fact|Proposed default|Assumption)[^\]]*\]", line_clean))
                if not has_tag:
                    untagged_count += 1

    # (f) Tags on non-requirement values (step numbers, IDs, section numbers)
    tags_on_non_req = 0
    bad_tag_patterns = [
        re.compile(r"^\s*\d+\.?\s*\[(?:Stated Fact|Proposed|Assumption)", re.MULTILINE | re.IGNORECASE),
        re.compile(r"\bStep\s+\d+\s*\[", re.IGNORECASE),
        re.compile(r"\b(?:FR|US|E)-\d+\s*\[", re.IGNORECASE),
        re.compile(r"Requirement ID:\s*(?:FR|US|E)-\d+\s*\[", re.IGNORECASE),
        re.compile(r"(?:##|Section)\s*[\d.]+\s*\[", re.IGNORECASE),
        re.compile(r"\b(?:BRD Section)\s*[\d.]+\s*\[", re.IGNORECASE),
    ]
    for line in all_lines:
        for pat in bad_tag_patterns:
            if pat.search(line):
                tags_on_non_req += 1

    # (g) BRD vs FRD conflicts for reminder, escalation, provisioning timing
    def extract_timing_facts(text: str) -> dict[str, set[str]]:
        facts: dict[str, set[str]] = {
            "provisioning": set(),
            "reminder": set(),
            "escalation": set(),
        }
        for m in re.finditer(r"(\d+\s*(?:hours?|days?))\s*(?:for|of)?\s*(?:it|asset|access|provisioning)", text, re.IGNORECASE):
            facts["provisioning"].add(m.group(1).lower())
        for m in re.finditer(r"provision.*?within\s+(\d+\s*(?:hours?|days?))", text, re.IGNORECASE):
            facts["provisioning"].add(m.group(1).lower())
        for m in re.finditer(r"(\d+\s*(?:hours?|days?))\s*(?:reminder|notification)", text, re.IGNORECASE):
            facts["reminder"].add(m.group(1).lower())
        for m in re.finditer(r"remind.*?(\d+\s*(?:hours?|days?))", text, re.IGNORECASE):
            facts["reminder"].add(m.group(1).lower())
        for m in re.finditer(r"(\d+\s*(?:hours?|days?))\s*(?:escalation|sla)", text, re.IGNORECASE):
            facts["escalation"].add(m.group(1).lower())
        for m in re.finditer(r"escalat.*?(\d+\s*(?:hours?|days?))", text, re.IGNORECASE):
            facts["escalation"].add(m.group(1).lower())
        return facts

    brd_timings = extract_timing_facts(brd_data["body_text"])
    frd_timings = extract_timing_facts(frd_data["body_text"])

    timing_conflicts = 0
    for topic in ["provisioning", "reminder", "escalation"]:
        b_vals = brd_timings[topic]
        f_vals = frd_timings[topic]
        if b_vals and f_vals and b_vals != f_vals:
            timing_conflicts += 1

    # (h) Banned phrases and validator text inside body sections
    banned_phrase_count = 0
    for doc_data in [brd_data, frd_data, epics_data, est_data]:
        text_to_check = doc_data["body_text"]
        for phrase in BANNED_PHRASES:
            banned_phrase_count += len(re.findall(phrase, text_to_check, re.IGNORECASE))

        validator_leaks = re.findall(r"\[(HIGH|CRITICAL|MEDIUM|LOW)\]", text_to_check)
        banned_phrase_count += len(validator_leaks)
        val_meta_re = re.findall(
            r"(?:does not cite a valid BRD Section|lacks required technical element|not covered by any User Story|missing requirement detail|flagged during automated validation)",
            text_to_check,
            re.IGNORECASE,
        )
        banned_phrase_count += len(val_meta_re)

    # (i) Title sanity
    title_sanity_issues = 0
    docs_to_check = [
        ("BRD", brd_data["title"]),
        ("FRD", frd_data["title"]),
        ("Epics", epics_data["title"]),
        ("Estimation", est_data["title"]),
    ]
    for doc_name, title in docs_to_check:
        clean_title = title.strip()
        words = clean_title.split()
        if not (2 <= len(words) <= 8):
            title_sanity_issues += 1
            continue
        first_word = words[0].lower().strip(".,;:!?\"'()[]{}#")
        if first_word in STOPWORDS:
            title_sanity_issues += 1
            continue
        if clean_title.startswith("#"):
            title_sanity_issues += 1
            continue
        if clean_title.lower() == "untitled project":
            title_sanity_issues += 1
            continue

    return {
        "coverage_table": coverage_table,
        "total_stories_parsed": total_stories_parsed,
        "duplicate_story_ids": duplicate_story_ids,
        "stories_without_fr": stories_without_fr,
        "dangling_fr_count": dangling_fr_count,
        "dangling_frs": sorted(list(dangling_frs)),
        "untagged_numbers_with_units": untagged_count,
        "tags_on_non_requirement_values": tags_on_non_req,
        "brd_frd_timing_conflicts": timing_conflicts,
        "banned_phrases_count": banned_phrase_count,
        "title_sanity_issues": title_sanity_issues,
        "missing_metrics_details": missing_metrics_details,
        "doc_hashes": doc_hashes,
        "titles": {name: title for name, title in docs_to_check},
    }


def format_scoreboard(scores: dict[str, Any]) -> str:
    lines = [
        "=" * 80,
        "SDLC DOCUMENT GENERATION SCOREBOARD",
        "=" * 80,
        "(a) Requirement Coverage:",
        f"{'Category':<18} {'Input Items':>12} {'FR Covered':>12} {'Story Covered':>15} {'BRD Covered':>13}",
        "-" * 80,
    ]

    for cat in ["features", "workflow steps", "integrations", "constraints", "metrics", "Total"]:
        if cat in scores["coverage_table"]:
            row = scores["coverage_table"][cat]
            fr_str = str(row["fr_covered"]) if row["fr_covered"] is not None else "-"
            st_str = str(row["story_covered"]) if row["story_covered"] is not None else "-"
            brd_str = str(row["brd_covered"]) if row["brd_covered"] is not None else "-"
            lines.append(
                f"{cat.title():<18} {row['input_count']:>12} {fr_str:>12} {st_str:>15} {brd_str:>13}"
            )

    if scores.get("missing_metrics_details"):
        lines.append("-" * 80)
        lines.append("Metrics missing from Project Objectives or Success Criteria:")
        for m in scores["missing_metrics_details"]:
            lines.append(f"  * {m}")

    total_stories = scores.get("total_stories_parsed", 0)
    stories_no_fr = scores.get("stories_without_fr", 0)
    story_stat = f"{stories_no_fr} / {total_stories} stories parsed" if total_stories else str(stories_no_fr)

    lines.extend([
        "-" * 80,
        f"(b) Duplicate Story IDs:                    {scores['duplicate_story_ids']}",
        f"(c) Stories without FR ID:                  {story_stat}",
        f"(d) Dangling / Non-existent FR references:   {scores['dangling_fr_count']}",
        f"(e) Untagged numbers with units:            {scores['untagged_numbers_with_units']}",
        f"(f) Tags on non-requirement values:         {scores['tags_on_non_requirement_values']}",
        f"(g) BRD vs FRD timing conflicts:            {scores['brd_frd_timing_conflicts']}",
        f"(h) Banned phrases / validator leaks:       {scores['banned_phrases_count']}",
        f"(i) Title sanity issues:                    {scores['title_sanity_issues']}",
        "=" * 80,
    ])
    if scores.get("dangling_frs"):
        lines.append(f"Dangling FR IDs: {', '.join(scores['dangling_frs'])}")
    lines.append(f"Detected Titles: {scores.get('titles')}")
    if scores.get("doc_hashes"):
        lines.append("-" * 80)
        lines.append("Document SHA256 Hashes:")
        for doc_name in ["BRD", "FRD", "Epics", "Estimation"]:
            lines.append(f"  {doc_name:<11}: {scores['doc_hashes'].get(doc_name, 'N/A')}")
        if scores["doc_hashes"].get("BRD") == scores["doc_hashes"].get("Epics"):
            lines.append("  WARNING: BRD.docx and Epics_Stories.docx have IDENTICAL hashes! Script saved the same doc twice.")
        else:
            lines.append("  VERIFIED: All document hashes are distinct.")
    lines.append("=" * 80)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Score generated SDLC documents against input requirements.")
    parser.add_argument("--input", "-i", default="qa/test_inputs/onboarding_case.md", help="Path to input markdown file")
    parser.add_argument("--docs", "-d", help="Directory containing the four DOCX files")
    parser.add_argument("--brd", help="Path to BRD.docx")
    parser.add_argument("--frd", help="Path to FRD.docx")
    parser.add_argument("--epics", help="Path to Epics_Stories.docx")
    parser.add_argument("--estimation", help="Path to Project_Estimation.docx")
    parser.add_argument("--output", "-o", help="Optional output text file to save results")

    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.exists():
        sys.exit(f"Input file not found: {input_file}")

    if args.docs:
        docs_dir = Path(args.docs)
        brd_file = next(docs_dir.glob("*BRD*.docx"), docs_dir / "BRD.docx")
        frd_file = next(docs_dir.glob("*FRD*.docx"), docs_dir / "FRD.docx")
        epics_file = next(docs_dir.glob("*Epic*.docx"), docs_dir / "Epics_Stories.docx")
        est_file = next(docs_dir.glob("*Estimat*.docx"), docs_dir / "Project_Estimation.docx")
    else:
        brd_file = Path(args.brd or "BRD.docx")
        frd_file = Path(args.frd or "FRD.docx")
        epics_file = Path(args.epics or "Epics_Stories.docx")
        est_file = Path(args.estimation or "Project_Estimation.docx")

    missing = [str(f) for f in [brd_file, frd_file, epics_file, est_file] if not f.exists()]
    if missing:
        sys.exit(f"Missing required DOCX file(s): {', '.join(missing)}")

    scores = score_documents(
        input_path=input_file,
        brd_path=brd_file,
        frd_path=frd_file,
        epics_path=epics_file,
        estimation_path=est_file,
    )

    output_str = format_scoreboard(scores)
    print(output_str)

    if args.output:
        Path(args.output).write_text(output_str, encoding="utf-8")
        print(f"Saved scoreboard to {args.output}")


if __name__ == "__main__":
    main()
