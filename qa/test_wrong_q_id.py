import os, requests, json
from dotenv import load_dotenv
load_dotenv(override=True)
API_KEY = os.getenv("API_KEY", "").split(",")[0]
headers = {"Authorization": f"Bearer {API_KEY}"}
BASE_URL = "http://127.0.0.1:8000/api/requirements"

sess_res = requests.post(f"{BASE_URL}/start", json={"problem_statement": "Another problem statement just to test wrong question IDs clearly"}, headers=headers)
sess_id = sess_res.json()["session_id"] if sess_res.status_code == 200 else "unknown"

r = requests.post(f"{BASE_URL}/{sess_id}/answer-questions", json={"round": 1, "answers": [{"q_id": "QINVALID", "answer": "Valid ans"}]}, headers=headers)
passed = (r.status_code == 400) and ("must be answered" in r.text or "Expected" in r.text)
print(f"Evidence: {r.text[:150]}")

try:
    with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "r") as f:
        master = json.load(f)
    master["phase_2"]["tests"].append({"ID": "T-API-28", "Desc": "Wrong question IDs", "Expected": "400", "Actual": r.status_code, "PASS": "PASS" if passed else "FAIL", "Evidence": str(r.text)[:150]})
    with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "w") as f:
        json.dump(master, f, indent=2)
except Exception as e:
    pass
