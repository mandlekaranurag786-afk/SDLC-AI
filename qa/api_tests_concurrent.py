import os, threading, time, requests, json
from dotenv import load_dotenv

load_dotenv(override=True)
API_KEY = os.getenv("API_KEY", "").split(",")[0]
BASE_URL = "http://127.0.0.1:8000/api/requirements"
headers = {"Authorization": f"Bearer {API_KEY}"}

def record_res(id_, desc, expected, actual, passed):
    print(f"[{'PASS' if passed else 'FAIL'}] {id_}: {desc} (Expected: {expected}, Actual: {actual})")
    
# T-API-18: Double start
results = []
def worker():
    res = requests.post(f"{BASE_URL}/start", json={"problem_statement": "This is a concurrent double start test string. Must be at least 12 words to pass validation absolutely properly."}, headers=headers)
    results.append(res.json().get("session_id") if res.status_code == 200 else res.status_code)

t1 = threading.Thread(target=worker)
t2 = threading.Thread(target=worker)
t1.start()
t2.start()
t1.join()
t2.join()

unique_sessions = list(set([r for r in results if isinstance(r, str)]))
passed_double = len(unique_sessions) == 2
record_res("T-API-18", "Double-start sessions", "2 distinct sessions created or error", f"Results: {results}, Unique: {len(unique_sessions)}", passed_double)

# Write to results.json
try:
    with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "r") as f:
        data = json.load(f)
    if "phase_2" not in data: data["phase_2"] = {"tests": []}
    data["phase_2"]["tests"].append({"ID": "T-API-18", "Desc": "Double-start", "Expected": "2 sessions", "Actual": str(results), "PASS": "PASS" if passed_double else "FAIL"})
    with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "w") as f:
        json.dump(data, f, indent=2)
except Exception as e:
    print(f"JSON Error: {e}")
