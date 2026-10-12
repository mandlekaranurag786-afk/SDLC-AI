import re
from pathlib import Path

RUN_QA_DIR = Path("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa")

def read_txt(f):
    try:
        return (RUN_QA_DIR / f).read_text(encoding="utf-8")
    except:
        return ""

epics = read_txt("Epics_and_User_Stories.docx.txt")
est = read_txt("Project_Estimation.docx.txt")

out = []
out.append("== Epics Analysis ==")

lines = epics.splitlines()
found_total_sp = 0
found_total_sprints = 0
story_lines = len(re.findall(r'US-\d{3}', epics))

m_sp = re.search(r'Total Story Points:\s*(\d+)', epics)
if m_sp: found_total_sp = int(m_sp.group(1))

m_sprints = re.search(r'Estimated Sprints:\s*(\d+)', epics)
if m_sprints: found_total_sprints = int(m_sprints.group(1))

out.append(f"Recorded Total Story Points: {found_total_sp}")
out.append(f"Recorded Sprints in Epics: {found_total_sprints}")
out.append(f"Count of User Stories identified: {story_lines}")
out.append(f"Calculated Velocity: {found_total_sp / found_total_sprints if found_total_sprints else 0:.1f} per sprint")

out.append("\n== Estimation Analysis ==")
est_lines = est.splitlines()

sprint_table_rows = re.findall(r'(Sprint \d+.*?weeks)', est)
sprint_count_table = len(sprint_table_rows)
out.append(f"Sprint count from Sprint Table: {sprint_count_table}")

phase_sprint_match = re.search(r'Development.*?\((\d+) sprints\)', est)
phase_sprint = int(phase_sprint_match.group(1)) if phase_sprint_match else 0
out.append(f"Sprint count from Phase Summary: {phase_sprint}")

duration_match = re.search(r'Estimated Project Duration:\s*(\d+)\s*weeks', est)
duration_weeks = int(duration_match.group(1)) if duration_match else 0
out.append(f"Total weeks from text: {duration_weeks}")

do_epics_match = "YES" if found_total_sprints == phase_sprint else "NO"
out.append(f"Epics and Estimation agree on sprints: {do_epics_match}")

out.append("\n-- Cost Computations --")
role_data = []
for m in re.finditer(r'([A-Za-z/ ]{5,}?)(1)(\d{2,3})\$([0-9,]+)-\$([0-9,]+)\$([0-9,]+)-\$([0-9,]+)', est):
    role = m.group(1).strip()
    count = int(m.group(2))
    days = int(m.group(3))
    off_min = int(m.group(4).replace(',',''))
    off_max = int(m.group(5).replace(',',''))
    on_min = int(m.group(6).replace(',',''))
    on_max = int(m.group(7).replace(',',''))
    role_data.append((role, count, days, off_min, off_max, on_min, on_max))

off_total_min = 0
off_total_max = 0
on_total_min = 0
on_total_max = 0
exchange_rate = 85.0

# Extract totals printed in doc
doc_off_min = doc_off_max = doc_on_min = doc_on_max = doc_blend_min = doc_blend_max = 0

m_off = re.search(r'Offshore Team.*?INR\s*([0-9,]+).*?INR\s*([0-9,]+)', est)
if m_off:
    doc_off_min = int(m_off.group(1).replace(',',''))
    doc_off_max = int(m_off.group(2).replace(',',''))

m_on = re.search(r'Onshore Team.*?INR\s*([0-9,]+).*?INR\s*([0-9,]+)', est)
if m_on:
    doc_on_min = int(m_on.group(1).replace(',',''))
    doc_on_max = int(m_on.group(2).replace(',',''))

m_blend = re.search(r'Blended.*?INR\s*([0-9,]+).*?INR\s*([0-9,]+)', est)
if m_blend:
    doc_blend_min = int(m_blend.group(1).replace(',',''))
    doc_blend_max = int(m_blend.group(2).replace(',',''))

for r in role_data:
    role, count, days, off_cmin, off_cmax, on_cmin, on_cmax = r
    off_total_min += days * off_cmin * count
    off_total_max += days * off_cmax * count
    on_total_min += days * on_cmin * count
    on_total_max += days * on_cmax * count
    out.append(f"Role: {role} (count {count}, days {days}) | Off: ${off_cmin}-{off_cmax} | On: ${on_cmin}-{on_cmax}")

out.append("\n-- Totals Validation (Rate: 85) --")
out.append(f"Calculated Offshore Min: ${off_total_min} * 85 = INR {off_total_min * 85:,}")
out.append(f"Documented Offshore Min: INR {doc_off_min:,}")
out.append(f"Calculated Offshore Max: ${off_total_max} * 85 = INR {off_total_max * 85:,}")
out.append(f"Documented Offshore Max: INR {doc_off_max:,}")

out.append(f"\nCalculated Onshore Min: ${on_total_min} * 85 = INR {on_total_min * 85:,}")
out.append(f"Documented Onshore Min: INR {doc_on_min:,}")
out.append(f"Calculated Onshore Max: ${on_total_max} * 85 = INR {on_total_max * 85:,}")
out.append(f"Documented Onshore Max: INR {doc_on_max:,}")

blend_calc_min = int((off_total_min * 85 + on_total_min * 85) / 2)
blend_calc_max = int((off_total_max * 85 + on_total_max * 85) / 2)

out.append(f"\nCalculated Blended Min: INR {blend_calc_min:,}")
out.append(f"Documented Blended Min: INR {doc_blend_min:,}")
out.append(f"Calculated Blended Max: INR {blend_calc_max:,}")
out.append(f"Documented Blended Max: INR {doc_blend_max:,}")

with open(RUN_QA_DIR / "independent_recompute_output.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
    
print("Recomputation done!")
