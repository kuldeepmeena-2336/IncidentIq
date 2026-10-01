from fastapi import FastAPI
from pydantic import BaseModel

from app.agents.ingestion_agent import ingest_issue
from app.agents.retrieval_agent import retrieve_incidents
from app.services.database import init_db
from app.services.provider_router import provider_router


class IngestionRequest(BaseModel):
    issue: dict | None = None
    payload: dict | None = None


class RetrievalRequest(BaseModel):
    query: str


app = FastAPI(
    title="IncidentIQ Agentic API",
    version="0.1.0",
    description="Python + LangGraph incident ingestion and retrieval service with degraded-mode safety.",
)


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    llm_provider = provider_router.get_llm_provider()
    embedding_provider = provider_router.get_embedding_provider()
    degraded = not provider_router.is_available()
    return {
        "status": "ok",
        "service": "incidentiq-agentic",
        "degraded_mode": degraded,
        "llm_provider": llm_provider.name if llm_provider else None,
        "embedding_provider": embedding_provider.name if embedding_provider else None,
    }


@app.get("/status")
def status() -> dict:
    return health()


@app.get("/")
def root() -> dict:
    return {
        "message": "IncidentIQ Python + LangGraph migration is running.",
        "degraded_mode": not provider_router.is_available(),
        "endpoints": ["/health", "/status", "/providers", "/ingest", "/retrieve"],
    }


@app.post("/ingest")
def ingest_endpoint(request: IngestionRequest) -> dict:
    payload = request.payload or request.issue or {}
    if not payload:
        return {
            "final_status": "empty_payload",
            "confidence": 0.0,
            "fallback_mode": True,
            "summary": "No Jira payload data was provided.",
        }
    return ingest_issue(payload)


@app.post("/retrieve")
def retrieve_endpoint(request: RetrievalRequest) -> dict:
    if not request.query or not request.query.strip():
        return {
            "query": "",
            "summary": "No search query was provided.",
            "results": [],
            "confidence": 0.0,
            "fallback_mode": True,
        }
    return retrieve_incidents(request.query)


@app.get("/providers")
def provider_status() -> dict:
    return provider_router.status_summary()
