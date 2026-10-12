# SDLC Requirements Assistant - QA Report

## Phase 0 & 1: Audit and Smoke Tests
- Validated initial workspace. Found 20 automation tests.
- Tested API Keys behavior (Pass: invalid key gives 401).
- Existing test suite passed (76 tests, 1 expected dev failure).

## Phase 2: Missing API Tests
- Added and passed missing tests: 401 missing key headers, invalid inputs (unicode, whitespace, too short), ID mismatched answers.
- Discovered Concurrency Bug: `T-API-18` (Double-start session) caused the backend to create 2 distinct sessions instead of relying on a proper idempotency lock.

## Phase 3: Workflow and LLM Layer
- **LLM Run Telemetry:** ~8 LLM calls per full generation cycle. Model: `gpt-4o-mini`. Max tokens dynamically change (2000 for analysis, up to 12000 for refinement). Total E2E time: ~90-120s.
- **Robustness:** Truncated responses raise `LLMServiceError` instead of blindly parsing. Regex fallback for non-strict JSON is robust. Max 2 refinement iterations. State saved between phases so it is resumable if it fails.
- **Security:** Problem statements are correctly redacted in logs when debug is disabled (`[REDACTED]`).

## Phase 4: End-to-End UI Test
- Ran a browser subagent executing the complete Happy Path via Streamlit. Uploaded test inputs, clicked Analyze, answered questions perfectly, and downloaded 4 `.docx` files.
- Negative tests in Streamlit showed clean error banners (e.g. `Please answer all 5 questions`). 

## Phase 5: Generated Document Quality
- **A. Coverage:** Perfect. The problem statement asked for automated checklists, e-signatures, ServiceNow integrations, AWS, etc - ALL were captured.
- **B. Grounding:** Pending script text output.
- **C. Contradictions:** None detected. Generated constraints align naturally.
- **D. Traceability:** Excellent. `US-001 -> Epic E-001 -> FRD-001 -> BRD 5.1`. 
- **E. Arithmetic:** Full independent Python execution verified that Total Story Points, Sprint counts, Team Role sizes, and Blended Cost calculations are 100% mathematically correct. The LLM produced flawless pricing formulas without errors.
- **F. Estimate Realism:** Realistic. 6 Sprints for 6 Team members over 16 weeks to build an onboarding SaaS.
- **G. Placeholders & Leakage:** Checked for raw prompts slipping into docs — none found.
- **H. Formatting:** No raw markdown table character leaks. Tables were rendered natively into docx XML elements.
- **I. Depth:** Acceptance criteria correctly followed `Given / When / Then` strict structures.

## Phase 6: Validator Effectiveness
- Modifying `BRD_PROMPT` to deliberately omit Success Criteria and Constraints successfully triggered the python validator.
- `validate_documents_with_python` successfully returned `False` and provided specific `missing_constraint` and `missing_metric` warnings.
- The refinement chain was triggered but ultimately *failed* to patch the documents when the `BRD_PROMPT` was strongly poisoned; the issues persisted.

## Phase 7: Additional Scenarios
- Dynamically triggered `/start` on three diverse problem cases (S2 API Gateway, S3 Expense App, S4 Compliance Portal).
- The LLM dynamically scaled questions (between 6-8 per scenario) and customized the scoping correctly (e.g., asking specifically about accounting software for S3, and Maker-Checker transition challenges for S4).
- Extracted exact prompt logs to `qa/run_qa/scenarios.md`.

## Phase 8: Security and Non-Functional
- **Storage:** Stored normally as TEXT within SQLite via SQLAlchemy.
- **Payload Limits:** The Pydantic model (`class StartRequest`) enforces `min_length=1` but does *not* set `max_length`. Submitting 500,000 characters is accepted by the server, directly leading to potential DoS handling costs and massive LLM token exhaustion.
- **XSS Risks:** `streamlit_app/app.py` renders the state directly using `st.write`. Because Streamlit uses DOMPurify natively to safely render markdown, script injection and malicious HTML are sanitized natively, mitigating direct XSS.
