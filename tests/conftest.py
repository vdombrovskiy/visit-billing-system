import os

import pytest_asyncio

from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.modules.visits.models.outbox_event import OutboxEvent
from app.modules.visits.models.base import VisitsBase
from app.modules.billing.models.base import BillingBase

load_dotenv(Path(__file__).resolve().parents[1] / ".env.test")


@pytest_asyncio.fixture
async def visits_session_factory():
    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is missing from .env.test")

    engine = create_async_engine(database_url)

    async with engine.begin() as connection:
        await connection.run_sync(VisitsBase.metadata.drop_all)
        await connection.run_sync(VisitsBase.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield session_factory

    async with engine.begin() as connection:
        await connection.run_sync(VisitsBase.metadata.drop_all)

    await engine.dispose()

@pytest_asyncio.fixture
async def billing_session_factory():
    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        raise RuntimeError("TEST_DATABASE_URL is missing from .env.test")

    engine = create_async_engine(database_url)

    async with engine.begin() as connection:
        await connection.run_sync(BillingBase.metadata.drop_all)
        await connection.run_sync(BillingBase.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    yield session_factory

    async with engine.begin() as connection:
        await connection.run_sync(BillingBase.metadata.drop_all)

    await engine.dispose()
