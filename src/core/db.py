"""Database setup and session management."""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from src.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    # asyncpg caches prepared-statement plans per physical connection. Behind a
    # transaction-mode pooler (Supabase/pgbouncer) each transaction may land on a
    # different backend, so a cached plan can be replayed against a connection
    # whose schema changed -> InvalidCachedStatementError. Disable both the
    # asyncpg cache and the SQLAlchemy-dialect prepared-statement cache.
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# NOTE: Schema is owned by NestJS TypeORM.
# FastAPI MUST NOT call Base.metadata.create_all() or run Alembic migrations.
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
