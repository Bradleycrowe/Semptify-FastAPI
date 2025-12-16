"""
Semptify Database Module
Async SQLAlchemy with SQLite (dev) / PostgreSQL (prod) support.
Includes connection pooling configuration for production.
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Engine and session factory (lazy initialization)
_engine = None
_async_session_factory = None


def get_engine():
    """
    Get or create the async engine with proper connection pooling.
    
    Pool settings:
    - PostgreSQL: QueuePool with configurable size
    - SQLite: NullPool (SQLite doesn't support concurrent connections well)
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        is_sqlite = "sqlite" in settings.database_url
        
        # Connection pool configuration
        pool_config = {}
        if is_sqlite:
            # SQLite: disable pooling, use check_same_thread=False
            pool_config = {
                "poolclass": NullPool,
                "connect_args": {"check_same_thread": False},
            }
        else:
            # PostgreSQL: use connection pooling
            pool_config = {
                "poolclass": QueuePool,
                "pool_size": 5,  # Base connections
                "max_overflow": 10,  # Extra connections under load
                "pool_timeout": 30,  # Seconds to wait for connection
                "pool_recycle": 1800,  # Recycle connections after 30 min
                "pool_pre_ping": True,  # Verify connections before use
            }
        
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            **pool_config,
        )
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.
    
    Usage:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """
    Initialize the database - create all tables.
    Call this on startup.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """
    Close database connections.
    Call this on shutdown.
    """
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


from contextlib import asynccontextmanager


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    Use this in services/background tasks (not FastAPI routes).

    Usage:
        async with get_db_session() as db:
            user = await db.get(User, user_id)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
