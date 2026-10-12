import math
import re
from typing import Any

VELOCITY_PER_SPRINT = 15  # Story points per sprint
SPRINT_LENGTH_WEEKS = 2   # Weeks per sprint
SETUP_WEEKS = 1           # Discovery & Setup phase
QA_WEEKS = 2              # QA & Testing phase
UAT_WEEKS = 1             # UAT & Deployment phase


def compute_project_timeline(total_story_points: int) -> dict[str, Any]:
    """
    Computes sprint count, phase durations, total weeks, and working days
    deterministically from total story points using named constants.
    """
    sprints = math.ceil(total_story_points / VELOCITY_PER_SPRINT) if VELOCITY_PER_SPRINT > 0 else 1
    sprints = max(1, sprints)
    sprint_weeks = sprints * SPRINT_LENGTH_WEEKS
    total_weeks = SETUP_WEEKS + sprint_weeks + QA_WEEKS + UAT_WEEKS
    fulltime_days = total_weeks * 5

    return {
        "total_story_points": total_story_points,
        "sprints": sprints,
        "sprint_weeks": sprint_weeks,
        "setup_weeks": SETUP_WEEKS,
        "qa_weeks": QA_WEEKS,
        "uat_weeks": UAT_WEEKS,
        "total_weeks": total_weeks,
        "fulltime_days": fulltime_days,
    }


def recompute_epics_arithmetic(epics_md: str, velocity_per_sprint: int = VELOCITY_PER_SPRINT) -> str:
    """
    Parses individual user stories in epics_md, extracts story points per epic,
    recomputes total points per epic, overall backlog points, and estimated sprint count.
    Overwrites Summary Table and Backlog Summary in epics_md.
    """
    lines = epics_md.splitlines()
    epics_data: dict[str, dict[str, Any]] = {}
    current_epic_id = ""
    current_epic_name = ""

    epic_heading_re = re.compile(r"^##\s+(E-\d{3})\s*:\s*(.+)$")
    us_heading_re = re.compile(r"^###\s+(US-\d{3})\s*:\s*(.+)$")
    sp_re = re.compile(r"\*\*Story Points:\*\*\s*(\d+)", re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        m_epic = epic_heading_re.match(stripped)
        if m_epic:
            current_epic_id = m_epic.group(1)
            current_epic_name = m_epic.group(2).strip()
            if current_epic_id not in epics_data:
                epics_data[current_epic_id] = {
                    "name": current_epic_name,
                    "stories_count": 0,
                    "total_points": 0,
                }
            continue

        m_us = us_heading_re.match(stripped)
        if m_us:
            if current_epic_id in epics_data:
                epics_data[current_epic_id]["stories_count"] += 1
            continue

        m_sp = sp_re.search(stripped)
        if m_sp:
            points = int(m_sp.group(1))
            if current_epic_id in epics_data:
                epics_data[current_epic_id]["total_points"] += points

    total_backlog_points = sum(e["total_points"] for e in epics_data.values())
    timeline_info = compute_project_timeline(total_backlog_points)
    estimated_sprints = timeline_info["sprints"]

    # Overwrite Summary Table
    if epics_data:
        summary_table_rows = ["| Epic ID | Epic Name | Stories Count | Total Story Points |", "|---------|-----------|---------------|-------------------|"]
        for eid, edata in epics_data.items():
            summary_table_rows.append(f"| {eid} | {edata['name']} | {edata['stories_count']} | {edata['total_points']} |")
        summary_table_str = "\n".join(summary_table_rows)

        epics_md = re.sub(
            r"(## Summary Table\s*\n+)(?:\|[^\n]+\n+)+",
            r"\1" + summary_table_str + "\n\n",
            epics_md,
            flags=re.DOTALL
        )

    # Overwrite Backlog Summary totals
    if re.search(r"\*\*Total Story Points:\*\*", epics_md):
        epics_md = re.sub(
            r"\*\*Total Story Points:\*\*.*$",
            f"**Total Story Points:** {total_backlog_points}",
            epics_md,
            flags=re.MULTILINE
        )
    else:
        epics_md += f"\n\n**Total Story Points:** {total_backlog_points}"

    if re.search(r"\*\*Estimated Sprints:\*\*", epics_md):
        epics_md = re.sub(
            r"\*\*Estimated Sprints:\*\*.*$",
            f"**Estimated Sprints:** {estimated_sprints}",
            epics_md,
            flags=re.MULTILINE
        )
    else:
        epics_md += f"\n**Estimated Sprints:** {estimated_sprints}"

    return epics_md


def recompute_estimation_timeline(
    estimation_md: str,
    epics_md: str,
    constraint_weeks: int | None = None,
    frd_md: str = "",
) -> str:
    """
    Overwrites Sprint Breakdown table, Phase Summary, Total Timeline, Team Size,
    and Role Working Days in estimation_md with values computed deterministically from Epics story points
    and actual FR IDs parsed from the FRD.
    """
    from feature_flags import ENABLE_ESTIMATION_FR_ALIGNMENT

    # Parse total points from epics_md
    sp_match = re.search(r"\*\*Total Story Points:\*\*\s*(\d+)", epics_md)
    total_sp = int(sp_match.group(1)) if sp_match else 45
    timeline = compute_project_timeline(total_sp)

    sprints = timeline["sprints"]
    total_weeks = timeline["total_weeks"]
    fulltime_days = timeline["fulltime_days"]

    # 1. Overwrite Sprint Breakdown Table (2.1)
    sprint_table_rows = ["| Sprint | Duration | Focus Area | FRs Covered |", "|--------|----------|------------|-------------|"]

    actual_fr_ids: list[str] = []
    if ENABLE_ESTIMATION_FR_ALIGNMENT:
        raw_ids = set(re.findall(r"\bFR-\d+\b", frd_md, re.IGNORECASE))
        if not raw_ids:
            raw_ids = set(re.findall(r"\bFR-\d+\b", epics_md, re.IGNORECASE))
        actual_fr_ids = sorted(list(raw_ids), key=lambda x: int(x.split("-")[1]))

    for i in range(1, sprints + 1):
        if ENABLE_ESTIMATION_FR_ALIGNMENT and actual_fr_ids:
            # Distribute actual FR IDs across sprints
            count_per_sprint = math.ceil(len(actual_fr_ids) / sprints)
            start_idx = (i - 1) * count_per_sprint
            end_idx = min(i * count_per_sprint, len(actual_fr_ids))
            chunk = actual_fr_ids[start_idx:end_idx]
            if len(chunk) == 1:
                fr_coverage = chunk[0]
            elif len(chunk) > 1:
                fr_coverage = f"{chunk[0]} to {chunk[-1]}"
            else:
                fr_coverage = "Hardening & Integration"
        else:
            fr_coverage = f"FR-{(i-1)*3+1:03d} to FR-{i*3:03d}"

        sprint_table_rows.append(f"| Sprint {i} | 2 weeks | Phase {i} Implementation | {fr_coverage} |")
    sprint_table_str = "\n".join(sprint_table_rows)

    estimation_md = re.sub(
        r"(### 2\.1 Sprint Breakdown\s*\n+)(?:\|[^\n]+\n+)+",
        r"\1" + sprint_table_str + "\n\n",
        estimation_md,
        flags=re.DOTALL
    )

    # 2. Overwrite Phase Summary (2.2)
    phase_summary_str = (
        "### 2.2 Phase Summary\n"
        f"- **Discovery & Setup:** {SETUP_WEEKS} week\n"
        f"- **Development & Sprint Execution ({sprints} sprints):** {timeline['sprint_weeks']} weeks\n"
        f"- **QA & Testing:** {QA_WEEKS} weeks\n"
        f"- **UAT & Deployment:** {UAT_WEEKS} week\n"
    )
    estimation_md = re.sub(
        r"### 2\.2 Phase Summary.*?(?=\n###|\n##|\Z)",
        phase_summary_str + "\n",
        estimation_md,
        flags=re.DOTALL
    )

    # 3. Overwrite Total Timeline (2.3)
    timeline_str = (
        "### 2.3 Total Timeline\n"
        f"**Estimated Project Duration:** {total_weeks} weeks ({fulltime_days} working days across {sprints} sprints).\n"
    )
    if constraint_weeks and total_weeks > constraint_weeks:
        timeline_str += f"\n> ⚠️ **Timeline Constraint Warning:** Estimated duration of {total_weeks} weeks exceeds constraint of {constraint_weeks} weeks.\n"

    estimation_md = re.sub(
        r"### 2\.3 Total Timeline.*?(?=\n###|\n##|\Z)",
        timeline_str + "\n",
        estimation_md,
        flags=re.DOTALL
    )

    # 4. Overwrite Table 4.1 Effort Breakdown (Working Days column per role)
    # Recalculate working days = allocation * total_weeks * 5
    lines = estimation_md.splitlines()
    new_lines = []
    in_effort_table = False
    role_pattern = re.compile(
        r"^\|\s*(.*?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\$?[^|]+)\s*\|\s*(\$?[^|]+)\s*\|$"
    )

    for line in lines:
        stripped = line.strip()
        if "4.1 Effort Breakdown" in stripped:
            in_effort_table = True
            new_lines.append(line)
            continue
        if in_effort_table and stripped.startswith("## 4.2"):
            in_effort_table = False
            new_lines.append(line)
            continue

        if in_effort_table:
            match = role_pattern.match(stripped)
            if match:
                role, count_str, old_days, off_rate, on_rate = match.groups()
                # Determine allocation: part-time/shared = 50%, full-time = 100%
                alloc = 0.5 if "part-time" in role.lower() or "shared" in role.lower() else 1.0
                computed_role_days = math.ceil(alloc * fulltime_days)
                new_line = f"| {role} | {count_str} | {computed_role_days} | {off_rate} | {on_rate} |"
                new_lines.append(new_line)
                continue

        new_lines.append(line)

    estimation_md = "\n".join(new_lines)
    return estimation_md


def recompute_estimation_cost(
    estimation_md: str,
    target_currency: str = "USD",
    user_budget: float | None = None
) -> str:
    """
    Parses Table 4.1 Effort Breakdown in estimation_md, recomputes offshore, onshore,
    and blended cost ranges, converts to target_currency using exchange rates,
    and overwrites Table 4.2 Total Cost Range.
    If user_budget is specified and estimated minimum cost exceeds user_budget,
    appends a Budget Risk Warning block to the report.
    Raises ValueError if placeholders like 'XX' or 'TBD' remain in cost tables.
    """
    from currency_utils import convert_from_usd, format_currency, check_budget_risk, EXCHANGE_RATES

    lines = estimation_md.splitlines()
    in_effort_table = False
    offshore_low_usd = 0.0
    offshore_high_usd = 0.0
    onshore_low_usd = 0.0
    onshore_high_usd = 0.0
    found_rows = 0

    role_row_pattern = re.compile(
        r"^\|\s*(.*?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*\$?([\d,]+)\s*-\s*\$?([\d,]+)\s*\|\s*\$?([\d,]+)\s*-\s*\$?([\d,]+)\s*\|$"
    )

    for line in lines:
        stripped = line.strip()
        if "4.1 Effort Breakdown" in stripped:
            in_effort_table = True
            continue
        if in_effort_table and (stripped.startswith("## 4.2") or stripped.startswith("### 4.2")):
            in_effort_table = False
            continue

        if in_effort_table:
            match = role_row_pattern.match(stripped)
            if match:
                found_rows += 1
                role, count_str, days_str, off_low_str, off_high_str, on_low_str, on_high_str = match.groups()
                count = int(count_str)
                days = int(days_str)
                off_low = float(off_low_str.replace(",", ""))
                off_high = float(off_high_str.replace(",", ""))
                on_low = float(on_low_str.replace(",", ""))
                on_high = float(on_high_str.replace(",", ""))

                offshore_low_usd += count * days * off_low
                offshore_high_usd += count * days * off_high
                onshore_low_usd += count * days * on_low
                onshore_high_usd += count * days * on_high

    if found_rows > 0:
        blended_low_usd = (offshore_low_usd + onshore_low_usd) / 2.0
        blended_high_usd = (offshore_high_usd + onshore_high_usd) / 2.0

        # Convert to target currency
        curr = target_currency.upper()
        off_low_curr = convert_from_usd(offshore_low_usd, curr)
        off_high_curr = convert_from_usd(offshore_high_usd, curr)
        on_low_curr = convert_from_usd(onshore_low_usd, curr)
        on_high_curr = convert_from_usd(onshore_high_usd, curr)
        blend_low_curr = convert_from_usd(blended_low_usd, curr)
        blend_high_curr = convert_from_usd(blended_high_usd, curr)

        off_str = f"{format_currency(off_low_curr, curr)} - {format_currency(off_high_curr, curr)}"
        on_str = f"{format_currency(on_low_curr, curr)} - {format_currency(on_high_curr, curr)}"
        blend_str = f"{format_currency(blend_low_curr, curr)} - {format_currency(blend_high_curr, curr)}"

        rate_note = ""
        if curr != "USD":
            rate_val = EXCHANGE_RATES.get(curr, 1.0)
            rate_note = f"\n*Note: Exchange rate assumption: 1 USD = {rate_val:.2f} {curr}.*\n"

        cost_table_str = (
            f"| Scenario | Estimated Cost ({curr}) |\n"
            "|----------|---------------|\n"
            f"| Offshore Team | {off_str} |\n"
            f"| Onshore Team | {on_str} |\n"
            f"| Blended (50/50) | {blend_str} |\n"
            f"{rate_note}"
        )

        estimation_md = re.sub(
            r"### 4\.2 Total Cost Range.*?(?=\n###|\n##|\Z)",
            f"### 4.2 Total Cost Range\n\n{cost_table_str}\n",
            estimation_md,
            flags=re.DOTALL
        )

        # Budget Risk Warning check
        has_risk, warning_msg = check_budget_risk(off_low_curr, user_budget, curr)
        if has_risk:
            warning_block = f"\n\n### 4.4 Budget Risk Warning\n\n> ⚠️ {warning_msg}\n\n"
            estimation_md += warning_block

    # Fail loudly if placeholders exist in cost text
    cost_section_match = re.search(r"4\.2 Total Cost Range.*?(?=##|\Z)", estimation_md, re.DOTALL)
    if cost_section_match:
        section_text = cost_section_match.group(0)
        if re.search(r"\bXX\b|TBD|\[insert|lorem|\$XX", section_text, re.IGNORECASE):
            raise ValueError("Estimation report contains unresolved cost placeholders!")

    return estimation_md
