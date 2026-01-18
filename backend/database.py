"""Database connection and session management."""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Database URL - defaults to local dev, override with env var in production
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://samyrlaguerre@localhost:5432/people_search"
)

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


async def get_db():
    """Dependency that provides a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
