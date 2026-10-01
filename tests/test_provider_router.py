from app.services.provider_router import provider_router


def test_provider_router_reports_degraded_mode_without_keys():
    summary = provider_router.status_summary()

    assert summary["degraded_mode"] is True
    assert summary["configured_providers"] == []
    assert summary["preferred_llm"] is None
    assert summary["preferred_embedding"] is None


def test_provider_router_builds_no_adapter_when_unconfigured():
    adapter = provider_router.get_llm_adapter()
    assert adapter is None

    adapter = provider_router.get_embedding_adapter()
    assert adapter is None
