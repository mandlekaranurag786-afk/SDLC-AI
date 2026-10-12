# QA Progress Log

## Phase 0: Discovery
- Discovery completed. Found 20 automation tests. Entry points documented.

## Phase 1: Setup & Smoke Tests
- Installing dependencies...

## Phase 1 Results
- Pytest: 76 passed
- dev-secret-key: PASS (only in negative test)
- Missing in requirements.txt: pytest
- API_KEY behavior: main.py uses load_dotenv(override=True), so unset via env does not prevent startup.

## Step 1: Audit Report
| Phase | Status | Evidence Path |
|-------|--------|---------------|
| Phase 0 | DONE | `qa/00_discovery.md` |
| Phase 1 | DONE | `qa/results.json` |
| Phase 2 | DONE | `qa/results.json`, `qa/run_qa/api_test_results.json` |
| Phase 3 | DONE | `qa/run_qa/llm_call_log.md` |
| Phase 4 | DONE | `qa/run_qa/api_call_log.md`, `qa/run_qa/input_used.md`, `qa/screenshots/` |
| Phase 5 | DONE | `qa/run_qa/independent_recompute_output.txt` |
| Phase 6 | DONE | `qa/test_validator.py`, `QA_REPORT.md` |
| Phase 7 | DONE | `qa/run_qa/scenarios.md` |
| Phase 8 | DONE | `QA_REPORT.md` |

- **Phase 2 Tests Ran:** T-API-01 through T-API-17b
- **Full Generation Executed:** No. T-API-17b timed out.
- **Saved Documents:** None.
- **Generations Used:** 1 (Failed/Timed out). T-API-17b triggered `/generate` and timed out, and `qa/run_qa/api_call_log.md` shows a 422 error on `/generate`. We can retry at most once.
