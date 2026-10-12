# SDLC Requirements Assistant — Remediation Changelog

## Round 2 Remediation Changes

### 1. Auth Hardening & Session Ownership (`auth.py`, `db.py`, `main.py`)
- **Fix**: Removed default fallback `API_KEY` in `auth.py`. App now raises `RuntimeError` on startup if `API_KEY` is not set in environment variables. Added `owner_id` column to `RequirementSession` and verified ownership in `require_session()`: returns HTTP 404 for sessions owned by other users. Configured explicit CORS middleware via `ALLOWED_ORIGINS` env var.
- **Reason**: Security hardening; prevents default credential vulnerability, prevents unauthorized cross-session data leakage, and enforces CORS boundary controls.
- **Tests**: `tests/test_r2_auth_hardening.py` (4/4 passed).

### 2. Opt-In Logging & Data Privacy (`integration_utils.py`, `main.py`)
- **Fix**: Replaced default prompt and traceback logging with explicit opt-in flags `ENABLE_PROMPT_LOGGING` and `ENABLE_TRACEBACK_LOGGING` (default `false`). Relocated log directory from `qa/logs/` to root `logs/`. Added raw problem statement redaction in prompt logs unless `ENABLE_DEBUG_LOGGING=true`.
- **Reason**: Data privacy and hygiene; prevents sensitive prompt text from leaking into default disk storage.
- **Tests**: `tests/test_r2_logging.py` (3/3 passed).

### 3. Deterministic Document Checks (`deterministic_checks.py`, `agent.py`)
- **Fix**: Implemented `run_deterministic_checks()` scanning for:
  - Leaked reviewer/meta phrases (`shall be clarified`, `must be defined`, `must be specified`, `This concludes`, `ensure that all items`)
  - BRD vs FRD numeric rule conflicts on same topics (e.g. IT provisioning, reminder SLAs)
  - Epics vs Estimation sprint-count mismatches
  - Story -> FR ID and FR -> BRD Section traceability gaps
  - Integration technical detail requirements
- **Reason**: Guarantees zero reviewer leakage, eliminates inter-document contradictions, and feeds findings directly into the `validation_report` and DOCX cover page warning banner.
- **Tests**: `tests/test_r2_deterministic_checks.py` (6/6 passed).

### 4. Integration Technical Specifications (`deterministic_checks.py`)
- **Fix**: Added `check_integration_technical_details()` requiring external integrations in FRD to include technical specifications (Authentication, Protocol, Payload Format, Direction/Frequency, Error Handling) rather than high-level mentions alone. Flags missing specs as `HIGH` severity findings (`high_level_integration_only`).
- **Reason**: Technical completeness for engineering handover.
- **Tests**: `tests/test_r2_integrations.py` (2/2 passed).

### 5. Estimate & Sprint Consistency (`currency_utils.py`, `arithmetic_utils.py`)
- **Fix**: Implemented `synchronize_estimation_currency()` to enforce target currency symbols (INR `₹`, USD `$`, EUR `€`, GBP `£`) and rate notes uniformly across all estimation sections. Recomputed sprint counts and role working days deterministically.
- **Reason**: Eliminates currency symbol mismatches and sprint duration drift.
- **Tests**: `tests/test_r2_estimate_consistency.py` (4/4 passed).

### 6. Grounding & Provenance Tagging (`provenance_utils.py`)
- **Fix**: Implemented `tag_numeric_provenance()` and `check_untagged_numeric_rules()`. Automatically tags numbers in user input as `[Stated Fact: per user input]` and invented numbers as `[Assumption/Proposal: confirm]`. Pre-export validator flags untagged numbers.
- **Reason**: Provides auditability and prevents unverified LLM assumptions from being mistaken for hard facts.
- **Tests**: `tests/test_r2_grounding.py` (2/2 passed).

---

## Round 1 Remediation Summary
- **Fix 1 (Arithmetic)**: Implemented deterministic story point and cost recomputation (`arithmetic_utils.py`).
- **Fix 2 (Integrations)**: Enforced structured extraction and 1-retry fallback (`integration_utils.py`).
- **Fix 3 (Currency & Budget)**: Added multi-currency budget parsing and overrun risk warnings (`currency_utils.py`).
- **Fix 4 (Project Naming)**: Replaced naive word slicing with hierarchical resolution (`project_name_utils.py`).
- **Fix 5 (Authentication & Exception Handling)**: Created `auth.py` and global sanitized exception handler (`main.py`).
- **Fix 6 (Deterministic Pre-Export Checks)**: Integrated pre-export placeholder scanning, native table grid rendering, and cover page warning banners (`document_export.py`).

---

## Clarification on API Test Count Breakdown (20 vs 25)
- In the initial QA Report, **20 test functions** were defined in `qa/api_tests.py`. When executed under pytest, parameterized tests and multi-assert loops expand to **25 total test executions**. Both counts refer to the same test suite.

---

## Items Noticed But Deliberately Not Fixed (Preserved per Architecture Rules)
1. **LangGraph State Graph Structure**: Maintained single-node processing pipeline without altering agent topology or adding unnecessary LLM calls.
2. **Streamlit UI Frontend Architecture**: Maintained standard Streamlit session state and polling mechanisms without introducing heavy custom React components.
