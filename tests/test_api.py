"""API integration tests."""

import pytest
from httpx import AsyncClient, ASGITransport

from agentplane.api.main import app
from agentplane.core.db import init_async_db


@pytest.fixture(autouse=True)
async def setup_db():
    await init_async_db()


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_company_crud():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        resp = await client.post("/api/companies", json={"name": "TestCo"})
        assert resp.status_code == 200
        company = resp.json()
        assert company["name"] == "TestCo"

        # List
        resp = await client.get("/api/companies")
        assert len(resp.json()) >= 1

        # Get
        resp = await client.get(f"/api/companies/{company['id']}")
        assert resp.json()["id"] == company["id"]
