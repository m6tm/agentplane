"""Tests for the OANDA market data adapter."""

from unittest.mock import MagicMock, patch

import pytest

from agentplane.adapters.base import AdapterContext, AdapterResult
from agentplane.adapters.builtin.oanda import OandaAdapter


@pytest.fixture
def adapter():
    return OandaAdapter()


@pytest.fixture
def ctx():
    return AdapterContext(
        run_id="test-run",
        agent_id="agent-1",
        config={
            "action": "fetch_history",
            "symbol": "EUR_USD",
            "token": "test-token",
            "environment": "practice",
        },
    )


@pytest.mark.asyncio
async def test_oanda_fetch_history(adapter: OandaAdapter, ctx: AdapterContext):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "instrument": "EUR_USD",
        "granularity": "D",
        "candles": [
            {
                "time": "2026-06-22T00:00:00.000000000Z",
                "mid": {"o": "1.0800", "h": "1.0850", "l": "1.0790", "c": "1.0840"},
                "volume": 1000,
                "complete": True,
            },
            {
                "time": "2026-06-23T00:00:00.000000000Z",
                "mid": {"o": "1.0840", "h": "1.0860", "l": "1.0830", "c": "1.0850"},
                "volume": 1200,
                "complete": True,
            },
        ],
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await adapter.execute(ctx)

    assert result.success is True
    assert result.exit_code == 0
    import json

    payload = json.loads(result.stdout)
    assert len(payload["records"]) == 2
    assert payload["records"][-1]["close"] == 1.085


@pytest.mark.asyncio
async def test_oanda_fetch_last_price(adapter: OandaAdapter):
    ctx = AdapterContext(
        run_id="test-run",
        agent_id="agent-1",
        config={
            "action": "fetch_last_price",
            "symbol": "EUR_USD",
            "token": "test-token",
            "account_id": "acc-1",
            "environment": "practice",
        },
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "prices": [
            {
                "instrument": "EUR_USD",
                "closeoutBid": "1.0840",
                "closeoutAsk": "1.0842",
            }
        ]
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await adapter.execute(ctx)

    assert result.success is True
    import json

    payload = json.loads(result.stdout)
    assert payload["price"] == 1.0841


@pytest.mark.asyncio
async def test_oanda_probe_missing_token(adapter: OandaAdapter):
    result = await adapter.probe({})
    assert result["available"] is False
    assert "token" in result["note"].lower()


@pytest.mark.asyncio
async def test_oanda_probe_with_token(adapter: OandaAdapter):
    mock_response = MagicMock()

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await adapter.probe({"token": "test-token"})

    assert result["available"] is True


@pytest.mark.asyncio
async def test_oanda_uses_settings_fallback_for_token(monkeypatch):
    monkeypatch.setattr("agentplane.adapters.builtin.oanda.settings.oanda_token", "env-token")
    monkeypatch.setattr(
        "agentplane.adapters.builtin.oanda.settings.oanda_account_id", "env-account"
    )

    adapter = OandaAdapter()
    ctx = AdapterContext(
        run_id="test-run",
        agent_id="agent-1",
        config={
            "action": "fetch_history",
            "symbol": "EUR_USD",
            "environment": "practice",
        },
    )

    called = {}

    async def fake_fetch(host, token, symbol, config):
        called["token"] = token
        called["host"] = host
        return AdapterResult(success=True, stdout='{"records":[]}', exit_code=0)

    adapter._fetch_history = fake_fetch
    await adapter.execute(ctx)
    assert called["token"] == "env-token"
