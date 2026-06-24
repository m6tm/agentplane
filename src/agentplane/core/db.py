"""Database engine and session management."""

from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

from agentplane.core.config import settings

# Ensure data directory exists
Path(settings.data_dir).mkdir(parents=True, exist_ok=True)

# Use aiosqlite for async SQLite
DATABASE_URL = settings.database_url
if DATABASE_URL.startswith("sqlite:///"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

engine = create_engine(DATABASE_URL, echo=settings.debug)
async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=settings.debug)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def init_db() -> None:
    """Create all tables synchronously."""
    SQLModel.metadata.create_all(engine)


async def init_async_db() -> None:
    """Create all tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


@asynccontextmanager
async def get_async_session():
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_session():
    """Yield a sync database session."""
    with Session(engine) as session:
        yield session
