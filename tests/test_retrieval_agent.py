from app.agents.retrieval_agent import retrieve_incidents


def test_retrieval_agent_uses_structured_and_semantic_fallback():
    result = retrieve_incidents("database connection pool exhausted")

    assert result["fallback_mode"] is True
    assert result["provider_used"] == "database_search"
    assert isinstance(result["results"], list)
    assert len(result["results"]) >= 1
    assert result["confidence"] >= 0.0
