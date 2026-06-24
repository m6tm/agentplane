"""Test configuration.

Every test runs against a fresh in-memory SQLite database so the local
`data/agentplane.db` file is never polluted by the test suite.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from agentplane.core import db


@pytest.fixture(autouse=True)
async def isolated_test_database():
    """Replace the global DB engines with an in-memory SQLite instance."""
    original_engine = db.engine
    original_async_engine = db.async_engine
    original_async_session_local = db.AsyncSessionLocal

    test_engine = create_engine("sqlite:///:memory:")
    test_async_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    test_async_session_local = sessionmaker(
        bind=test_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    db.engine = test_engine
    db.async_engine = test_async_engine
    db.AsyncSessionLocal = test_async_session_local

    # Create tables in the in-memory database
    SQLModel.metadata.create_all(test_engine)
    async with test_async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield

    # Restore original engines
    db.engine = original_engine
    db.async_engine = original_async_engine
    db.AsyncSessionLocal = original_async_session_local

    await test_async_engine.dispose()
    test_engine.dispose()
