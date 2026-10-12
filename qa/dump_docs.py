import re, zipfile
from pathlib import Path

RUN_QA_DIR = Path("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa")
files = ["BRD.docx", "FRD.docx", "Epics_and_User_Stories.docx", "Project_Estimation.docx"]

for f in files:
    path = RUN_QA_DIR / f
    if not path.exists():
        print(f"NOT FOUND: {f}")
        continue
    
    with zipfile.ZipFile(path, 'r') as docx:
        if 'word/document.xml' in docx.namelist():
            xml = docx.read('word/document.xml').decode('utf-8')
            # remove formatting tags to get linear text roughly
            text = re.sub(r'<w:p [^>]*>', '\n', xml)
            text = re.sub(r'<w:r [^>]*>', '', text)
            text = re.sub(r'<[^>]+>', '', text)
            
            with open(RUN_QA_DIR / f"{f}.txt", 'w', encoding='utf-8') as out:
                out.write(text)
    
    print(f"Dumped {f}.txt")
