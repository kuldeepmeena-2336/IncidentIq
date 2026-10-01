# IncidentIQ Agentic Python Migration

This project is the Python + LangGraph replacement for the legacy Java/SpringBoot implementation.

## Current status
- Python project scaffold created
- Provider abstraction added for OpenAI, Azure OpenAI, and OpenAI-compatible/Gemini-compatible endpoints
- Fallback ingestion and retrieval modes are working without external API keys
- SQLite-backed persistence and structured search are in place
- Postgres-ready migration and vector store scaffolding added

## Stack
- Python 3.12+
- FastAPI
- LangGraph
- SQLAlchemy
- SQLite for local dev
- Postgres-ready schema for migration

## Run locally
1. Create a virtual environment
2. Install dependencies: `pip install -r requirements.txt`
3. Start the app: `uvicorn app.main:app --reload`
4. Test: `pytest -q`

## Key endpoints
- `GET /health`
- `GET /providers`
- `POST /ingest`
- `POST /retrieve`

## Migration notes
The project is intentionally designed to run in degraded mode until provider configuration is supplied. This keeps the system testable and operational even when Azure/OpenAI/Gemini keys are absent.
