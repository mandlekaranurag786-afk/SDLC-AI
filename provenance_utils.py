import re
from typing import Any

NUMBER_UNIT_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(%|(?:days?|hours?|hrs?|sprints?|weeks?|months?|years?|percent|mb|gb|tb|seconds?|mins?|minutes?|lakhs?|crores?|k)\b)?",
    re.IGNORECASE
)


def extract_numeric_facts_with_units(user_input: str) -> set[tuple[str, str]]:
    """
    Extracts (numeric_value, unit) pairs from user input text.
    For example: ("4", "hours"), ("3", "days"), ("90", "%").
    """
    if not user_input:
        return set()

    matches = NUMBER_UNIT_PATTERN.findall(user_input)
    facts = set()
    for num, unit in matches:
        clean_num = str(float(num) if "." in num else int(num))
        clean_unit = unit.lower().strip() if unit else ""
        facts.add((clean_num, clean_unit))
        # Also store bare number for simple matches
        facts.add((clean_num, ""))
    return facts


def extract_numbers_from_input(user_input: str) -> set[str]:
    if not user_input:
        return set()
    nums = re.findall(r"\d+(?:\.\d+)?", user_input)
    return set(nums)


from feature_flags import ENABLE_PROVENANCE_TAG_FILTERING


def tag_numeric_provenance(doc_text: str, user_input: str) -> str:
    """
    Appends provenance tags [Stated Fact: per user input] or [Proposed default — confirm]
    to numeric requirement statements with units in document text.
    Never tags step numbers (Step 1), requirement IDs (FR-001, US-001), section headers, or dates.
    """
    if not doc_text:
        return doc_text

    input_facts = extract_numeric_facts_with_units(user_input)
    input_nums = extract_numbers_from_input(user_input)

    lines = doc_text.splitlines()
    tagged_lines = []
    in_kpi_section = False

    for line in lines:
        stripped = line.strip()

        if "## 11. Success Criteria" in line or "Success Metrics" in line:
            in_kpi_section = True
            tagged_lines.append(line)
            continue
        elif stripped.startswith("## ") and in_kpi_section:
            in_kpi_section = False

        if not stripped or stripped.startswith("#") or "|" in stripped or "Traceability" in stripped:
            tagged_lines.append(line)
            continue

        if any(skip_kw in line for skip_kw in ["Requirement ID:", "BRD Mapping:", "Version:", "Generated Date:", "Page "]):
            tagged_lines.append(line)
            continue

        if ENABLE_PROVENANCE_TAG_FILTERING:
            # Strip any bad tags accidentally on non-requirement tokens
            line = re.sub(r"(?i)\b(Step\s+\d+)\s*\[(?:Stated Fact|Proposed|Assumption)[^\]]*\]", r"\1", line)
            line = re.sub(r"(?i)\b((?:FR|US|E)-\d+)\s*\[(?:Stated Fact|Proposed|Assumption)[^\]]*\]", r"\1", line)
            line = re.sub(r"(?i)(Requirement ID:\s*(?:FR|US|E)-\d+)\s*\[(?:Stated Fact|Proposed|Assumption)[^\]]*\]", r"\1", line)
            line = re.sub(r"(?i)((?:##|Section|BRD Section)\s*[\d.]+)\s*\[(?:Stated Fact|Proposed|Assumption)[^\]]*\]", r"\1", line)
            line = re.sub(r"(?m)^\s*(\d+\.?)\s*\[(?:Stated Fact|Proposed|Assumption)[^\]]*\]", r"\1", line)

            matches = list(re.finditer(
                r"\b(\d+(?:\.\d+)?)\s*(%|(?:days?|hours?|hrs?|sprints?|weeks?|months?|years?|percent|mb|gb|tb|seconds?|mins?|minutes?|lakhs?|crores?|k)\b)",
                line,
                re.IGNORECASE,
            ))
        else:
            if "[Stated Fact" in line or "[Assumption" in line or "[Proposed default" in line:
                tagged_lines.append(line)
                continue
            matches = list(NUMBER_UNIT_PATTERN.finditer(line))

        if not matches:
            tagged_lines.append(line)
            continue

        line_tagged = line
        for match in reversed(matches):
            raw_val = match.group(1)
            raw_unit = (match.group(2) or "").lower().strip()
            clean_num = str(float(raw_val) if "." in raw_val else int(raw_val))

            start_pos = match.start()
            end_pos = match.end()

            if ENABLE_PROVENANCE_TAG_FILTERING:
                preceding = line_tagged[max(0, start_pos - 15):start_pos].lower()
                if any(preceding.endswith(kw) for kw in ["step ", "phase ", "section ", "sprint ", "version ", "fr-", "us-", "e-"]):
                    continue
                if start_pos > 0 and line_tagged[start_pos - 1] in "-/":
                    continue
                following = line_tagged[end_pos:end_pos + 40]
                if re.match(r"^\s*\[(?:Stated Fact|Proposed|Assumption)", following):
                    continue

            if raw_unit:
                is_stated = (clean_num, raw_unit) in input_facts
            else:
                is_stated = (clean_num, "") in input_facts or raw_val in input_nums

            if is_stated:
                tag = " [Stated Fact: per user input]"
            else:
                tag = " [Assumption/Proposal: confirm]"

            if not line_tagged[end_pos:].startswith(" ["):
                line_tagged = line_tagged[:end_pos] + tag + line_tagged[end_pos:]

        tagged_lines.append(line_tagged)

    return "\n".join(tagged_lines)


def check_untagged_numeric_rules(doc_text: str, user_input: str, doc_name: str) -> list[dict[str, Any]]:
    """
    Finds numeric statements with units not present in user input that are missing provenance tags.
    """
    issues = []
    if not doc_text:
        return issues

    input_facts = extract_numeric_facts_with_units(user_input)

    for line_idx, line in enumerate(doc_text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "|" in stripped or "Traceability" in stripped:
            continue

        if any(skip_kw in line for skip_kw in ["Requirement ID:", "BRD Mapping:", "Version:", "Generated Date:", "Page "]):
            continue

        if "[Stated Fact" in line or "[Assumption" in line or "[Proposed default" in line:
            continue

        matches = re.findall(
            r"\b(\d+(?:\.\d+)?)\s*(%|(?:days?|hours?|hrs?|sprints?|weeks?|months?|years?|percent|mb|gb|tb|seconds?|mins?|minutes?|lakhs?|crores?|k)\b)",
            line,
            re.IGNORECASE,
        )
        for num, unit in matches:
            clean_num = str(float(num) if "." in num else int(num))
            clean_unit = unit.lower().strip()
            if (clean_num, clean_unit) not in input_facts:
                issues.append({
                    "type": "untagged_numeric_assumption",
                    "severity": "MEDIUM",
                    "section": doc_name,
                    "affected_requirement": f"Line {line_idx}",
                    "recommendation": f"Numeric value '{num} {unit}' on line {line_idx} is not in user input and lacks provenance tag ([Assumption/Proposal: confirm] or [Proposed default — confirm])."
                })
                break
    return issues
