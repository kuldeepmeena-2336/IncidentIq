from app.services.search_service import IncidentSearchService


def test_search_service_filters_and_ranks():
    service = IncidentSearchService()
    results = service.search("payment timeout", filters={"service": "payments"}, limit=5)

    assert len(results) >= 1
    assert results[0]["service"] == "payments"
    assert results[0]["score"] >= 0.0


def test_search_service_without_filters_returns_seed_data():
    service = IncidentSearchService()
    results = service.search("database connection")

    assert len(results) >= 1
    assert any(result["failure_type"] == "database_connection" for result in results)
