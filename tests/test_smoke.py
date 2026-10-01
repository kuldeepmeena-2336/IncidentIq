from app.agents.ingestion_agent import ingest_issue
from app.agents.retrieval_agent import retrieve_incidents


def test_ingestion_fallback_smoke():
    payload = {
        "issue": {
            "id": "INC-2001",
            "summary": "Payment API timeout during checkout",
            "description": "Customers are seeing payment gateway timeouts after login flow",
        }
    }
    result = ingest_issue(payload)

    assert result["final_status"] in {"stored", "partial_record_stored"}
    assert result["confidence"] >= 0.0
    assert result["fallback_mode"] is True


def test_retrieval_fallback_smoke():
    result = retrieve_incidents("payment timeout")

    assert result["confidence"] >= 0.0
    assert result["summary"].startswith("Search completed")
    assert result["fallback_mode"] is True
