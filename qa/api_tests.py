import os, sys, time, json, requests
from dotenv import load_dotenv

load_dotenv(override=True)
API_KEY = os.getenv("API_KEY", "").split(",")[0]
if not API_KEY:
    print("NO API KEY IN ENV")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000/api/requirements"

results = []
def record(id_, desc, expected, actual, passed, evidence=""):
    res = {"ID": id_, "Desc": desc, "Expected": expected, "Actual": actual, "PASS": "PASS" if passed else "FAIL", "Evidence": evidence}
    results.append(res)
    print(f"[{res['PASS']}] {id_}: {desc} (Expected: {expected}, Actual: {actual})")
    if evidence: print(f"  -> Evidence: {evidence}")

def get_headers(auth_type="bearer", key=API_KEY):
    if auth_type == "bearer":
        return {"Authorization": f"Bearer {key}"}
    elif auth_type == "x-api":
        return {"X-API-Key": key}
    elif auth_type == "malformed":
        return {"Authorization": "Bearer"}
    return {}

headers = get_headers()
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
record("T-API-17a", "Start Happy Path", "200", start_res.status_code, start_res.status_code == 200, "Session ID: " + start_res.json().get("session_id", ""))

if start_res.status_code == 200:
    data = start_res.json()
    sess_id = data["session_id"]
    api_call_logs = [(f"POST /start", problem_statement)]
    
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
            
            payload = {"answers": answ, "round": current_round}
            api_call_logs.append((f"POST /answer-questions (Round {current_round})", json.dumps(payload)))
            ans_res = requests.post(f"{BASE_URL}/{sess_id}/answer-questions", json=payload, headers=headers, timeout=120)
            print(f"  -> Answered Round {current_round}: {ans_res.status_code}")
            
            if ans_res.status_code == 200:
                data = ans_res.json()
                current_round += 1
            else:
                record("T-API-17b", "Happy Path Generating", "Completed", ans_res.status_code, False, ans_res.text)
                break
        
        elif status == "ready_for_generation":
            print("  -> Ready for generation")
            break

    # Trigger generate!
    print("  -> Triggering Generation...")
    try:
        gen_res = requests.post(f"{BASE_URL}/{sess_id}/generate", json={"approval_type": "both"}, headers=headers, timeout=300)
        print(f"  -> Generated: {gen_res.status_code}")
        api_call_logs.append(("POST /generate", str(gen_res.status_code)))
        
        if gen_res.status_code == 200:
            record("T-API-17b", "Happy Path Generating", "Completed", 200, True)
        else:
            record("T-API-17b", "Happy Path Generating", "Completed", gen_res.status_code, False, gen_res.text)
    except Exception as e:
        record("T-API-17b", "Happy Path Generating", "Completed", "Exception", False, str(e))
    
    # Write api call logs
    with open("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa/api_call_log.md", "w") as f:
        for action, payload in api_call_logs:
            f.write(f"### {action}\n```\n{payload}\n```\n\n")

print("\n--- Summary ---")
with open("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa/api_test_results.json", "w") as f:
    json.dump(results, f, indent=2)

try:
    with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "r") as f:
        master = json.load(f)
except:
    master = {}
if "phase_2" not in master: master["phase_2"] = {"tests": []}
master["phase_2"]["tests"].extend(results)
with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "w") as f:
    json.dump(master, f, indent=2)
