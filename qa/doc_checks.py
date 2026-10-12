import os, json, re, zipfile
from pathlib import Path

# Paths to evaluate
RUN_QA_DIR = Path("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa")
files = ["BRD.docx", "FRD.docx", "Epics_and_User_Stories.docx", "Project_Estimation.docx"]

results = {
    "A_Coverage": [],
    "B_Grounding": [],
    "C_Internal_Contradictions": [],
    "D_Traceability": [],
    "E_Arithmetic": [],
    "F_Estimate_Realism": [],
    "G_Placeholders": [],
    "H_Formatting": [],
    "I_Depth": []
}

def extract_xml_and_text(docx_name):
    path = RUN_QA_DIR / docx_name
    if not path.exists(): return "", "", []
    lines = []
    xml_content = ""
    tables_count = 0
    try:
        with zipfile.ZipFile(path, 'r') as docx_zip:
            if 'word/document.xml' in docx_zip.namelist():
                xml_content = docx_zip.read('word/document.xml').decode('utf-8')
                tables_count = xml_content.count("<w:tbl>")
                # Extract text using regex to simulate naive line extraction
                texts = re.findall(r'<w:t(?: xml:space="[^"]*")?>(.*?)</w:t>', xml_content)
                lines = [t for t in texts if t.strip()]
    except Exception as e:
        print(f"Error unzipping {path}: {e}")
    return lines, xml_content, tables_count

doc_texts = {}
doc_tables = {}
for f in files:
    l, c, tbls = extract_xml_and_text(f)
    doc_texts[f] = l
    doc_tables[f] = tbls

# A. Coverage
# Heuristics checking list.
# Will check later.

# G. Placeholders & Leakage
for f, lines in doc_texts.items():
    for line_idx, line in enumerate(lines):
        line_num = line_idx + 1
        lower_line = line.lower()
        for ph in ["xx", "tbd", "todo", "[insert", "lorem", "shall be clarified", "must be defined", "must be specified", "this concludes", "ensure that all items"]:
            if ph in lower_line:
                # Except if 'xx' is in normal words. Let's use word boundary for exact matches.
                if ph == "xx" and not re.search(r'\bxx\b', lower_line): continue
                results["G_Placeholders"].append({
                    "finding": f"Placeholder '{ph}' found",
                    "file": f,
                    "line": line_num,
                    "text": line
                })

# H. Formatting
for f in files:
    results["H_Formatting"].append({
        "finding": f"Total tables",
        "file": f,
        "count": doc_tables.get(f, 0)
    })
    for i, line in enumerate(doc_texts.get(f, [])):
        if "|" in line and "-" in line: # raw markdown table text
            results["H_Formatting"].append({
                "finding": "Raw markdown table character '|' found",
                "file": f,
                "line": i+1,
                "text": line
            })

with open("/home/anurag-mandlekar/Desktop/SDLC/qa/doc_checks_results.json", "w") as out:
    json.dump(results, out, indent=2)

print("Check script ran. Results in doc_checks_results.json")
