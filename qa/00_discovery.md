# Phase 0 - Discovery

## Architecture & Entry Points
- **Backend Entry Point**: `uvicorn main:app`
- **Streamlit Entry Point**: `streamlit run app.py`
- **Backend Port**: 8000 (uvicorn default)
- **Frontend Port**: 8501 (streamlit default)

## Configuration
- **API Keys**: Loaded from the `API_KEY` environment variable (comma-separated string parsing) in `auth.py`, evaluated via `verify_api_key`. Keys are not printed directly. Stored temporarily in `request.state.owner_id`.
- **CORS Settings**: Bound by `ALLOWED_ORIGINS` in `.env`, defaulting to `http://localhost:8501,http://localhost:3000`, applied via FastAPI's `CORSMiddleware`.
- **DB Location**: SQLite at `requirements.db` in the repository root.
- **Log Flags**: Opt-in flags for debugging:
  - `ENABLE_PROMPT_LOGGING` (prompt output tracking)
  - `ENABLE_TRACEBACK_LOGGING` (dump stack traces on 500 errors to `logs/backend.log`)
  - `ENABLE_DEBUG_LOGGING`

## API Routes
| Method | Path | Auth | Request/Response description |
|---|---|---|---|
| GET | `/health` | No | Basic 200 OK |
| GET | `/api/health` | No | Basic 200 OK |
| POST | `/api/requirements/start` | Yes | Body: `StartRequest` (problem schema). Returns state/session. |
| POST | `/api/requirements/{session_id}/answer-questions` | Yes | Body: `AnswerQuestionsRequest`. Submits clarifications. |
| POST | `/api/requirements/{session_id}/generate` | Yes | Body: `GenerateRequest`. Initiates document generation. |
| GET | `/api/requirements/{session_id}/download/estimation` | Yes | Returns `.docx` for estimation. |
| GET | `/api/requirements/{session_id}/download/epics-stories` | Yes | Returns `.docx` for epics. |
| POST | `/api/requirements/{session_id}/prototype` | Yes | Generates prototype HTML file. |
| GET | `/api/requirements/{session_id}/download/prototype` | Yes | Downloads HTML file. |
| GET | `/api/requirements/{session_id}/download/{doc_type}` | Yes | Downloads `brd` or `frd` as Word document. |
| GET | `/api/requirements/{session_id}` | Yes | Retrieves current session state block. |

## Workflow Nodes
The LLM workflow follows `agent.py`:
1. `analyze_requirements`: Calls LLM to check `problem_statement` completeness.
2. `generate_clarifying_questions`: Ask clarification questions (Limit: 5 rounds).
3. `generate_brd`: Generates Executive Summary & Scope. (Max tokens: 5000, Model default: `gpt-4o-mini`)
4. `generate_epics_stories`: Extracts epics from BRD. (Max tokens: 7000)
5. `generate_frd`: Generates Functional Requirements from BRD and Epics. (Max tokens: 7000)
6. `validate_completeness`: Compares output and determines defects.
7. `refine_documents`: Iterates generation based on validation payload. (Max refinement iterations limit: 2 tokens 12000)
8. `_run_parallel_exports`: Runs parallel generation for artifacts like `estimation` (Max tokens 4000).
9. `generate_prototype`: Takes FRD block and constructs visual prototype screens.

Pending clarification inputs are stored inside the `RequirementSession` model (`pending_questions` structured field). Evaluation happens via checking max count <=5 before failing.

## Existing Automated Tests
- Located in `tests/` directory with 20 defined `test_*.py` files.
- Command executed: `pytest --collect-only -q` returned `127` due to virtual environment not existing. We will install dependencies in Phase 1 before running the full test suite.
