import requests, os

from dotenv import load_dotenv
load_dotenv(override=True)
API_KEY = os.environ.get("API_KEY", "").split(",")[0]
headers = {"Authorization": f"Bearer {API_KEY}"}
URL = "http://127.0.0.1:8000/api/requirements/start"

scenarios = [
    {
        "id": "S2",
        "desc": "B2B API gateway",
        "ps": "We need a new B2B API gateway to handle high-throughput third-party partner traffic securely, including centralized authentication, rate limiting, and detailed partner billing analytics."
    },
    {
        "id": "S3",
        "desc": "Internal expense claim app",
        "ps": "Employees are currently submitting paper-based expense claim forms. We want an internal expense claim application where they can upload receipts, track approval workflows from their reporting manager, and automatically integrate with the finance ERP for payout."
    },
    {
        "id": "S4",
        "desc": "Heavy regulatory compliance portal",
        "ps": "We must build a heavy regulatory compliance portal for the financial sector. It requires deep audit logging, real-time data encryption, Maker-Checker strict workflows, and automated quarterly reporting generation to the SEC."
    }
]

out = ["# Additional Scenarios (Phase 7)"]

for s in scenarios:
    res = requests.post(URL, json={"problem_statement": s["ps"]}, headers=headers, timeout=60)
    data = res.json()
    questions = data.get("questions") or data.get("next_questions", [])
    
    out.append(f"\n## Scenario {s['id']}: {s['desc']}")
    out.append(f"**Problem Statement input:** {s['ps']}")
    out.append("**Clarification Questions generated:**")
    for i, q in enumerate(questions, 1):
        out.append(f"{i}. {q['question']}")

os.makedirs("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa", exist_ok=True)
with open("/home/anurag-mandlekar/Desktop/SDLC/qa/run_qa/scenarios.md", "w") as f:
    f.write("\n".join(out))

print("Scenarios completed.")
