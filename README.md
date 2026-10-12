# SDLC AI BRD/FRD Generation Agent

FastAPI + LangGraph service that turns a problem statement into BRD and FRD Word documents. If the statement is incomplete, the service asks five clarifying questions per round and persists the HIL loop in SQLite.

## Run Comamnd

frontend - streamlit run app.py
backend - uvicorn main:app --reload

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="your-groq-api-key"
uvicorn main:app --reload
```

Optional environment variables:

```bash
export GROQ_MODEL="llama-3.3-70b-versatile"
export DATABASE_URL="sqlite:///./requirements.db"
export DOCX_OUTPUT_DIR="generated_docs"
```

## API Flow

1. Start a session:

```bash
curl -X POST http://127.0.0.1:8000/api/requirements/start \
  -H "Content-Type: application/json" \
  -d '{"problem_statement":"We need a system that allows construction estimators to upload tender PDFs and automatically extract material lists, reducing manual data entry time from 6 hours to under 15 minutes."}'
```

2. Answer all five questions if returned:

```bash
curl -X POST http://127.0.0.1:8000/api/requirements/{session_id}/answer-questions \
  -H "Content-Type: application/json" \
  -d '{"round":1,"answers":[{"q_id":"Q1","answer":"..."},{"q_id":"Q2","answer":"..."},{"q_id":"Q3","answer":"..."},{"q_id":"Q4","answer":"..."},{"q_id":"Q5","answer":"..."}]}'
```

3. Generate BRD and FRD:

```bash
curl -X POST http://127.0.0.1:8000/api/requirements/{session_id}/generate \
  -H "Content-Type: application/json" \
  -d '{"approval_type":"both"}'
```

4. Download documents:

```bash
curl -OJ http://127.0.0.1:8000/api/requirements/{session_id}/download/brd
curl -OJ http://127.0.0.1:8000/api/requirements/{session_id}/download/frd
```

## Files

- `main.py`: FastAPI endpoints.
- `agent.py`: LangGraph node functions and generation pipeline.
- `prompts.py`: Prompt templates.
- `state_schema.py`: LangGraph state schema.
- `db.py`: SQLAlchemy persistence.
- `document_export.py`: Markdown to `.docx` export.
