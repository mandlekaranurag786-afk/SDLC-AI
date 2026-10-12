#!/usr/bin/env python3
import os
import sys
import time
import argparse
from pathlib import Path
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path("/home/anurag-mandlekar/Desktop/SDLC")
load_dotenv(PROJECT_ROOT / ".env", override=True)

raw_key = os.getenv("API_KEY", "")
api_key = raw_key.split(",")[0].strip() if raw_key else ""
headers = {"Authorization": f"Bearer {api_key}"}
BASE_URL = "http://127.0.0.1:8000/api/requirements"


def wait_for_server(timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get("http://127.0.0.1:8000/health", timeout=2)
            if r.status_code == 200:
                print("Server is healthy.")
                return True
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Server failed to respond to /health within timeout.")


def run_generation_flow(output_dir: Path, input_md_path: Path):
    wait_for_server()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_md = input_md_path.read_text(encoding="utf-8")

    q_map = {
        "q1": input_md.split("# Q1.")[1].split("# Q2.")[0].strip(),
        "q2": input_md.split("# Q2.")[1].split("# Q3.")[0].strip(),
        "q3": input_md.split("# Q3.")[1].split("# Q4.")[0].strip(),
        "q4": input_md.split("# Q4.")[1].split("# Q5.")[0].strip(),
        "q5": input_md.split("# Q5.")[1].strip(),
    }
    problem_statement = input_md.split("# Q1.")[0].strip().replace("# Problem Statement\n", "").strip()

    print("--> Starting requirements session...")
    start_res = requests.post(
        f"{BASE_URL}/start",
        json={"problem_statement": problem_statement},
        headers=headers,
        timeout=180,
    )
    if start_res.status_code != 200:
        sys.exit(f"Start failed: {start_res.status_code} {start_res.text}")

    data = start_res.json()
    sess_id = data["session_id"]
    print(f"Session ID: {sess_id}")

    current_round = 1
    max_rounds = 5
    for rnd in range(max_rounds):
        status = data.get("status")
        print(f"Current status: {status}")
        if status in ["asking_questions", "more_questions_needed"]:
            questions = data.get("questions") or data.get("next_questions", [])
            answ = []
            for q in questions:
                q_text = q.get("question", "").lower()
                if "feature" in q_text or "functionality" in q_text:
                    ans_text = q_map["q1"]
                elif "workflow" in q_text or "role" in q_text or "step" in q_text:
                    ans_text = q_map["q2"]
                elif "integrat" in q_text or "system" in q_text:
                    ans_text = q_map["q3"]
                elif "constraint" in q_text or "limit" in q_text:
                    ans_text = q_map["q4"]
                elif "metric" in q_text or "success" in q_text:
                    ans_text = q_map["q5"]
                else:
                    ans_text = f"{q_map['q1']}\n{q_map['q2']}\n{q_map['q3']}\n{q_map['q4']}\n{q_map['q5']}"
                answ.append({"q_id": q.get("id"), "answer": ans_text})

            ans_res = requests.post(
                f"{BASE_URL}/{sess_id}/answer-questions",
                json={"answers": answ, "round": current_round},
                headers=headers,
                timeout=180,
            )
            print(f"  -> Answered Round {current_round}: {ans_res.status_code}")
            if ans_res.status_code == 200:
                data = ans_res.json()
                current_round += 1
            else:
                sys.exit(f"Answer failed: {ans_res.status_code} {ans_res.text}")

        elif status == "ready_for_generation":
            break

    print("--> Triggering Document Generation (approval_type='both')...")
    gen_res = requests.post(
        f"{BASE_URL}/{sess_id}/generate",
        json={"approval_type": "both"},
        headers=headers,
        timeout=600,
    )
    if gen_res.status_code != 200:
        sys.exit(f"Generate failed: {gen_res.status_code} {gen_res.text}")

    print("Generation complete! Downloading DOCX files...")
    # 1. BRD
    r = requests.get(f"{BASE_URL}/{sess_id}/download/brd", headers=headers, timeout=60)
    (output_dir / "BRD.docx").write_bytes(r.content)
    # 2. FRD
    r = requests.get(f"{BASE_URL}/{sess_id}/download/frd", headers=headers, timeout=60)
    (output_dir / "FRD.docx").write_bytes(r.content)
    # 3. Epics & Stories
    r = requests.get(f"{BASE_URL}/{sess_id}/download/epics-stories", headers=headers, timeout=60)
    (output_dir / "Epics_Stories.docx").write_bytes(r.content)
    # 4. Estimation
    r = requests.get(f"{BASE_URL}/{sess_id}/download/estimation", headers=headers, timeout=60)
    (output_dir / "Project_Estimation.docx").write_bytes(r.content)

    print(f"All 4 DOCX files saved to {output_dir}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", default="qa/baseline_docs", help="Directory to save downloaded DOCX files")
    parser.add_argument("--input", "-i", default="qa/test_inputs/onboarding_case.md", help="Path to input markdown file")
    args = parser.parse_args()

    out_path = PROJECT_ROOT / args.output
    in_path = PROJECT_ROOT / args.input
    run_generation_flow(out_path, in_path)


if __name__ == "__main__":
    main()
