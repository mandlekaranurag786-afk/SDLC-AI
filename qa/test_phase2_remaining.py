import os, sys, requests, json, time, subprocess, threading

BASE_URL = "http://127.0.0.1:8000/api/requirements"
results = []
def record(id_, desc, expected, actual, passed, evidence=""):
    res = {"ID": id_, "Desc": desc, "Expected": expected, "Actual": str(actual), "PASS": "PASS" if passed else "FAIL", "Evidence": str(evidence).replace("\n", " ")[:150]}
    results.append(res)
    print(f"[{res['PASS']}] {id_}: {desc} (Expected: {expected}, Actual: {actual})")
    try:
        with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "r") as f:
            master = json.load(f)
        master["phase_2"]["tests"].append(res)
        with open("/home/anurag-mandlekar/Desktop/SDLC/qa/results.json", "w") as f:
            json.dump(master, f, indent=2)
    except Exception as e:
        print("JSON Error", e)

from dotenv import load_dotenv
load_dotenv(override=True)
API_KEY = os.getenv("API_KEY", "").split(",")[0]
headers = {"Authorization": f"Bearer {API_KEY}"}

print("Creating session for tests...")
try:
    sess_res = requests.post(f"{BASE_URL}/start", json={"problem_statement": "Valid statement with enough length to pass the validation check simply."}, headers=headers, timeout=120)
    sess_id = sess_res.json()["session_id"] if sess_res.status_code == 200 else "unknown"
except Exception:
    sess_id = "unknown"

for url_suffix, payload, method in [
    ("/answer-questions", {"round": 1, "answers": []}, "POST"),
    ("/generate", {"approval_type": "both"}, "POST"),
    ("/download/brd", None, "GET")
]:
    url = f"{BASE_URL}/{sess_id}{url_suffix}"
    for hdrs, desc in [({}, "No key"), ({"Authorization": "Bearer BAD_KEY"}, "Wrong key"), ({"Authorization": "Bearer"}, "Malformed header")]:
        suffix = "answer" if "answer" in url else ("generate" if "generate" in url else "download")
        tid = f"T-API-401-{suffix}-{desc.replace(' ', '')}"
        try:
            if method == "POST": r = requests.post(url, json=payload, headers=hdrs, timeout=120)
            else: r = requests.get(url, headers=hdrs, timeout=120)
            actual = r.status_code
        except Exception as e: actual = str(e)
        record(tid, f"401 on {suffix} with {desc}", "401", actual, actual == 401)

def t_api(id_, payload, desc, expected_status):
    try:
        r = requests.post(f"{BASE_URL}/start", json=payload, headers=headers, timeout=120)
        record(id_, desc, str(expected_status), r.status_code, r.status_code == expected_status, evidence=r.text)
    except Exception as e:
        record(id_, desc, str(expected_status), "Error", False, str(e))

t_api("T-API-20a", {"problem_statement": "    \n\t   "}, "/start with whitespace", 400)
t_api("T-API-20b", {"problem_statement": "Valid statement with emoji 😊🔥 over 12 words to pass validation nicely"}, "/start with unicode/emoji", 200)

try:
    r_ans1 = requests.post(f"{BASE_URL}/{sess_id}/answer-questions", json={"round": 1, "answers": [{"q_id": "Q1", "answer": ""}]}, headers=headers, timeout=120)
    record("T-API-21a", "Empty string answer", "4xx", r_ans1.status_code, r_ans1.status_code in [400, 422], r_ans1.text)
except: pass

try:
    r_ans2 = requests.post(f"{BASE_URL}/{sess_id}/answer-questions", json={"round": 1, "answers": [{"q_id": "Q1", "answer": "Some valid answer text goes here"}]}, headers=headers, timeout=120)
    record("T-API-21b", "Missing answers", "400", r_ans2.status_code, r_ans2.status_code == 400, r_ans2.text)
except: pass

try:
    r_ans3 = requests.post(f"{BASE_URL}/{sess_id}/answer-questions", json={"round": 5, "answers": [{"q_id": "Q1", "answer": "text"}]}, headers=headers, timeout=120)
    ok_text = ("None" not in r_ans3.text) and ("Expected answers for round 1" in r_ans3.text)
    record("T-API-21c", "Wrong round message does not say None", "No None string", str(r_ans3.status_code), ok_text, r_ans3.text)
except: pass

sessions_created = []
def make_sess():
    try:
        r = requests.post(f"{BASE_URL}/start", json={"problem_statement": "A very uniquely distinct string to make it work properly for validation"}, headers=headers, timeout=120)
        if r.status_code == 200: sessions_created.append(r.json().get("session_id"))
    except: pass
threads = [threading.Thread(target=make_sess) for _ in range(3)]
for t in threads: t.start()
for t in threads: t.join(timeout=15)
record("T-API-24", "Three parallel sessions", "Isolated", "Lengths of list: " + str(len(set(sessions_created))), len(set(sessions_created)) == 3)

ds_results = []
def double_worker():
    try:
        r = requests.post(f"{BASE_URL}/start", json={"problem_statement": "This is a concurrent double start test string. Must be at least 12 words to pass validation absolutely properly."}, headers=headers, timeout=120)
        ds_results.append(r.json().get("session_id") if r.status_code == 200 else r.status_code)
    except: pass
t1 = threading.Thread(target=double_worker)
t2 = threading.Thread(target=double_worker)
t1.start()
t2.start()
t1.join(timeout=15)
t2.join(timeout=15)
passed_double = len(set([x for x in ds_results if isinstance(x, str)])) == 2
record("T-API-18", "Double-start sessions", "2 distinct sessions", str(ds_results), passed_double)

env_without_key = os.environ.copy()
env_without_key.pop("API_KEY", None)
env_without_key.pop("API_KEYS", None)
p = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, '/home/anurag-mandlekar/Desktop/SDLC'); from auth import get_valid_api_keys; get_valid_api_keys()"], env=env_without_key, capture_output=True, text=True)
refused_without_key = (p.returncode != 0) and ("Required" in p.stderr or "empty" in p.stderr or "API_KEY" in p.stderr)
record("T-API-26", "Startup refusal without a key", "Error raised CODE-LEVEL", "Return Code: " + str(p.returncode), refused_without_key, p.stderr[-100:])

print("Done")
