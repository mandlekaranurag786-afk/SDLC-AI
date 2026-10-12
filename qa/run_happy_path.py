import os, sys, requests, json, time

BASE_URL = "http://127.0.0.1:8000/api/requirements"
results = []
def record(id_, desc, expected, actual, passed, evidence=""):
    print(f"[{'PASS' if passed else 'FAIL'}] {id_}: {desc}")

from dotenv import load_dotenv
load_dotenv(override=True)
API_KEY = os.getenv("API_KEY", "").split(",")[0]
headers = {"Authorization": f"Bearer {API_KEY}"}

input_md = ""
with open("/home/anurag-mandlekar/Desktop/SDLC/qa/test_inputs/onboarding_case.md", "r") as f:
    input_md = f.read()

q_map = {
    "q1": input_md.split("# Q1.")[1].split("# Q2.")[0].strip(),
    "q2": input_md.split("# Q2.")[1].split("# Q3.")[0].strip(),
    "q3": input_md.split("# Q3.")[1].split("# Q4.")[0].strip(),
    "q4": input_md.split("# Q4.")[1].split("# Q5.")[0].strip(),
    "q5": input_md.split("# Q5.")[1].strip()
}
problem_statement = input_md.split("# Q1.")[0].strip().replace("# Problem Statement\n", "").strip()

print("--> Starting Happy Path (T-API-17)")
start_res = requests.post(f"{BASE_URL}/start", json={"problem_statement": problem_statement}, headers=headers, timeout=120)
if start_res.status_code != 200:
    print(f"Start failed: {start_res.text}")
    sys.exit(1)

data = start_res.json()
sess_id = data["session_id"]
print(f"Session ID: {sess_id}")

current_round = 1
max_rounds = 5
for rnd in range(max_rounds):
    status = data.get("status")
    if status in ["asking_questions", "more_questions_needed"]:
        questions = data.get("questions") or data.get("next_questions", [])
        answ = []
        for q in questions:
            q_text = q.get("question", "").lower()
            if "feature" in q_text or "functionality" in q_text: ans_text = q_map["q1"]
            elif "workflow" in q_text or "role" in q_text or "step" in q_text: ans_text = q_map["q2"]
            elif "integrat" in q_text or "system" in q_text: ans_text = q_map["q3"]
            elif "constraint" in q_text or "limit" in q_text: ans_text = q_map["q4"]
            elif "metric" in q_text or "success" in q_text: ans_text = q_map["q5"]
            else: ans_text = q_map["q1"] + "\n" + q_map["q2"] + "\n" + q_map["q3"] + "\n" + q_map["q4"] + "\n" + q_map["q5"]
            answ.append({"q_id": q.get("id"), "answer": ans_text})
        
        ans_res = requests.post(f"{BASE_URL}/{sess_id}/answer-questions", json={"answers": answ, "round": current_round}, headers=headers, timeout=120)
        print(f"  -> Answered Round {current_round}: {ans_res.status_code}")
        
        if ans_res.status_code == 200:
            data = ans_res.json()
            current_round += 1
        else:
            print("Answer failed", ans_res.text)
            sys.exit(1)
    
    elif status == "ready_for_generation":
        break

print("  -> Triggering Generation...")
gen_res = requests.post(f"{BASE_URL}/{sess_id}/generate", json={"approval_type": "both"}, headers=headers, timeout=300)
print(f"  -> Generated: {gen_res.status_code}")

if gen_res.status_code == 200:
    record("T-API-17b", "Happy Path Generating", "Completed", 200, True)
else:
    print(gen_res.text)
    sys.exit(1)

# Write results
try:
    with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "r") as f:
        master = json.load(f)
    master["phase_2"]["tests"].append({"ID": "T-API-17b", "Desc": "Happy Path Generating", "Expected": "Completed", "Actual": "200", "PASS": "PASS", "Evidence": ""})
    with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "w") as f:
        json.dump(master, f, indent=2)
except Exception as e:
    print("Error saving result", e)

# Save documents (wait Phase 4 says "Download every artifact the UI offers as qa/run_qa/BRD.docx..." but Phase 2 says "skip if a valid one with saved documents already exists" - actually if I just do Phase 4, then I don't NEED to save docs here? Or I can save them here. Let me just save them to be safe.)
os.makedirs("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa", exist_ok=True)
brd_r = requests.get(f"{BASE_URL}/{sess_id}/download/brd", headers=headers)
with open("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa/BRD.docx", "wb") as f: f.write(brd_r.content)

frd_r = requests.get(f"{BASE_URL}/{sess_id}/download/frd", headers=headers)
with open("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa/FRD.docx", "wb") as f: f.write(frd_r.content)

epic_r = requests.get(f"{BASE_URL}/{sess_id}/download/epics-stories", headers=headers)
with open("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa/Epics_and_User_Stories.docx", "wb") as f: f.write(epic_r.content)

est_r = requests.get(f"{BASE_URL}/{sess_id}/download/estimation", headers=headers)
with open("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa/Project_Estimation.docx", "wb") as f: f.write(est_r.content)

try:
    proto_r = requests.post(f"{BASE_URL}/{sess_id}/prototype", headers=headers)
    if proto_r.status_code == 200:
        proto_dl = requests.get(f"{BASE_URL}/{sess_id}/download/prototype", headers=headers)
        with open("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa/prototype.html", "wb") as f: f.write(proto_dl.content)
except: pass

print("Documents saved.")
