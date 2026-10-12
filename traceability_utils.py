"""
traceability_utils.py

Deterministic traceability management:
1. Fix B.a: Globally renumber user stories across all epics (US-001 .. US-0xx)
   - Renumbers story headings, body self-references, and Backlog Summary table rows.
2. Fix B.b: Map story-to-FR links
   - Retains existing FR citations if present.
   - Maps missing FR citations using BRD Section mapping and/or title similarity to FRD requirements.
   - Injects standardized `**Traceability:** FR-xxx` into each story block.
   - Leaves unmapped stories unmapped and logs findings (never invents).

Controlled by feature flags:
- ENABLE_STORY_ID_RENUMBERING
- ENABLE_STORY_FR_LINKING
"""

import re
from typing import Any

from feature_flags import ENABLE_STORY_FR_LINKING, ENABLE_STORY_ID_RENUMBERING


STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by",
    "as", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "and", "or", "but", "so", "if", "that", "this",
    "user", "system", "i", "want", "so", "can", "able", "need", "allow"
}


def stem_word(w: str) -> str:
    w = w.lower()
    for suffix in ["ing", "tion", "tions", "ies", "es", "s", "ed", "ment", "ments"]:
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[:-len(suffix)]
    return w


def extract_frs_from_frd(frd_markdown: str) -> list[dict[str, Any]]:
    """Extract all functional requirements from FRD markdown with ID, title, description, and mapped BRD sections."""
    if not frd_markdown:
        return []

    # Matches ## FR-001: Title or FR-001: Title
    matches = list(re.finditer(r"(?m)^(?:#{1,3}\s+)?(FR-\d+)\s*:\s*(.+)$", frd_markdown, re.IGNORECASE))
    frs = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(frd_markdown)
        block = frd_markdown[start:end]
        fr_id = match.group(1).upper()
        raw_title = match.group(2).strip()
        clean_title = re.sub(r"^\*+|\*+$", "", raw_title).strip()

        # Title line override
        title_m = re.search(r"(?m)^\s*(?:\*\*)?Title(?:\*\*)?:\s*(.+)$", block, re.IGNORECASE)
        if title_m:
            clean_title = re.sub(r"^\*+|\*+$", "", title_m.group(1).strip()).strip()

        # Description
        desc_m = re.search(
            r"(?m)^\s*(?:\*\*)?Description(?:\*\*)?:\s*([^\n]+(?:\n(?!\s*(?:\*\*)?[A-Za-z\s]+(?:\*\*)?:)[^\n]+)*)",
            block,
            re.IGNORECASE,
        )
        desc = desc_m.group(1).strip() if desc_m else ""

        # BRD Section mapping (e.g. "Maps to BRD Section: 5.1" or "**BRD Mapping:** BRD Section 5.1")
        brd_sections = set(re.findall(r"(?:BRD\s+Section|Section)\s*[:\s]*([\d.]+)", block, re.IGNORECASE))

        frs.append({
            "id": fr_id,
            "title": clean_title,
            "description": desc,
            "brd_sections": brd_sections,
            "block": block,
        })
    return frs


def calculate_similarity(text_a: str, text_b: str) -> float:
    words_a = [stem_word(w) for w in re.findall(r"[A-Za-z0-9]+", text_a) if len(w) > 2 and w.lower() not in STOPWORDS]
    words_b = [stem_word(w) for w in re.findall(r"[A-Za-z0-9]+", text_b) if len(w) > 2 and w.lower() not in STOPWORDS]
    if not words_a or not words_b:
        return 0.0
    set_b = set(words_b)
    overlap = sum(1 for w in words_a if w in set_b)
    return overlap / max(len(words_a), 1)


def find_best_fr_for_story(
    story_title: str,
    story_body: str,
    epic_title: str,
    fr_list: list[dict[str, Any]],
) -> tuple[str | None, str]:
    """Finds the most appropriate FR for a story.
    Returns (fr_id, reason) or (None, reason).
    """
    if not fr_list:
        return None, "No FRs available"

    # 1. Existing FR cited in story body/title
    body_fr_match = re.search(r"\b(FR-\d+)\b", story_title + " " + story_body, re.IGNORECASE)
    if body_fr_match:
        existing_fr = body_fr_match.group(1).upper()
        # Verify it exists in FR list
        if any(fr["id"] == existing_fr for fr in fr_list):
            return existing_fr, "Existing FR citation in story"

    # 2. Check for BRD section in Epic or Story
    combined_text = f"{epic_title}\n{story_title}\n{story_body}"
    cited_sections = set(re.findall(r"(?:BRD\s+Section|Section)\s*[:\s]*([\d.]+)", combined_text, re.IGNORECASE))
    if cited_sections:
        candidates = [fr for fr in fr_list if fr["brd_sections"].intersection(cited_sections)]
        if len(candidates) == 1:
            return candidates[0]["id"], f"Direct BRD section mapping ({','.join(cited_sections)})"
        elif len(candidates) > 1:
            # Pick best candidate by title similarity
            best_c = max(candidates, key=lambda c: calculate_similarity(story_title, c["title"]))
            return best_c["id"], f"BRD section match ({','.join(cited_sections)}) with title alignment"

    # 3. Content similarity against FR title and description
    best_fr = None
    best_sim = 0.0
    for fr in fr_list:
        sim = calculate_similarity(f"{story_title} {story_body}", f"{fr['title']} {fr['description']}")
        if sim > best_sim:
            best_sim = sim
            best_fr = fr

    if best_fr and best_sim >= 0.25:
        return best_fr["id"], f"Semantic title/description alignment ({int(best_sim * 100)}%)"

    return None, "Unmapped"


def renumber_and_link_epics_stories(
    epics_markdown: str,
    frd_markdown: str = "",
) -> tuple[str, list[str]]:
    """Globally renumbers stories across all epics (US-001..US-0xx) and maps missing FR citations.
    Updates story headers, body references, and Backlog Summary table.
    """
    if not epics_markdown:
        return epics_markdown, []

    fr_list = extract_frs_from_frd(frd_markdown)
    findings: list[str] = []

    # Split into sections while keeping delimiters
    # Split by Epics or Story headings: ### US-xxx or ### User Story: US-xxx
    story_pattern = re.compile(
        r"(?m)^(#{2,4}\s*(?:User Story\s+)?)(US-\d+)(\s*:\s*)(.+)$",
        re.IGNORECASE,
    )

    story_matches = list(story_pattern.finditer(epics_markdown))
    if not story_matches:
        return epics_markdown, findings

    # Step 1: Detect Backlog Summary table to avoid renumbering header row inside the table
    backlog_m = re.search(r"(?m)^#{1,3}\s+Backlog Summary", epics_markdown, re.IGNORECASE)
    main_stories_end = backlog_m.start() if backlog_m else len(epics_markdown)

    # Filter story matches to only those in the main body (before backlog summary)
    body_matches = [m for m in story_matches if m.start() < main_stories_end]
    if not body_matches:
        body_matches = story_matches

    id_map: dict[str, str] = {}
    current_epic_title = "Epic"
    story_counter = 1

    # Split document by body_matches
    reconstructed_parts: list[str] = []
    last_end = 0

    for idx, match in enumerate(body_matches):
        prefix_chunk = epics_markdown[last_end:match.start()]
        # Check if an Epic heading was declared in prefix_chunk
        epic_heading_m = re.findall(r"(?m)^#{1,2}\s+(.+)$", prefix_chunk)
        if epic_heading_m:
            current_epic_title = epic_heading_m[-1].strip()

        reconstructed_parts.append(prefix_chunk)

        header_prefix = match.group(1)
        orig_id = match.group(2).upper()
        colon_sep = match.group(3)
        story_title = match.group(4).strip()

        # Determine new ID
        if ENABLE_STORY_ID_RENUMBERING:
            new_id = f"US-{story_counter:03d}"
            story_counter += 1
            id_map[orig_id] = new_id
        else:
            new_id = orig_id

        # Story content bounds
        story_end = body_matches[idx + 1].start() if idx + 1 < len(body_matches) else main_stories_end
        story_body = epics_markdown[match.end():story_end]

        # Fix B.b: Link to FR
        if ENABLE_STORY_FR_LINKING:
            matched_fr, reason = find_best_fr_for_story(
                story_title=story_title,
                story_body=story_body,
                epic_title=current_epic_title,
                fr_list=fr_list,
            )

            # Check if Traceability already exists in story_body
            tr_pattern = re.compile(r"(?m)^\s*(?:\*\*)?Traceability(?:\*\*)?:\s*.*$", re.IGNORECASE)
            if tr_pattern.search(story_body):
                if matched_fr:
                    # Standardize format: **Traceability:** FR-xxx
                    story_body = tr_pattern.sub(f"**Traceability:** {matched_fr}", story_body)
            else:
                if matched_fr:
                    # Append Traceability line
                    story_body = f"{story_body.rstrip()}\n\n**Traceability:** {matched_fr}\n\n"
                else:
                    findings.append(f"Story {new_id} ('{story_title}') remains unmapped to any FR: {reason}")

        # Assemble new heading and body
        new_heading = f"{header_prefix}{new_id}{colon_sep}{story_title}"
        reconstructed_parts.append(new_heading)
        reconstructed_parts.append(story_body)
        last_end = story_end

    # Append remaining text (including Backlog Summary table)
    remaining_text = epics_markdown[last_end:]

    # Step 2: Update Backlog Summary table rows with renumbered IDs if enabled
    if ENABLE_STORY_ID_RENUMBERING and id_map and remaining_text:
        # Renumber table cells: | US-001 | or | US-002 |
        # In the table, each row maps sequentially to the story sequence
        lines = remaining_text.splitlines(keepends=True)
        updated_lines = []
        table_story_counter = 1
        in_backlog_table = False

        for line in lines:
            if "|" in line:
                # Check if line contains US-\d+
                if re.search(r"\|\s*US-\d+\s*\|", line, re.IGNORECASE):
                    in_backlog_table = True
                    # Replace with sequential US-xxx
                    rep_id = f"US-{table_story_counter:03d}"
                    table_story_counter += 1
                    line = re.sub(r"\|\s*US-\d+\s*\|", f"| {rep_id} |", line, count=1, flags=re.IGNORECASE)
            updated_lines.append(line)
        remaining_text = "".join(updated_lines)

    reconstructed_parts.append(remaining_text)
    final_markdown = "".join(reconstructed_parts)
    return final_markdown, findings
