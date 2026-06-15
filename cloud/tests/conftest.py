"""
conftest.py — 测试共用 fixtures
提供异步 SQLite 内存数据库, 每次测试前后自动建表/清理。
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from database import Base
from models.task import PrintTask
from models.node import PrintNode


# ── 内存 SQLite 引擎 + 会话工厂 ─────────────
TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def async_engine():
    """创建独立的内存引擎, 测试结束后 dispose"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(async_engine):
    """为每个测试创建独立事务, 测试后回滚"""
    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
