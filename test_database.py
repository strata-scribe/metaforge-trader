import pytest
import pytest_asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database import Base, Item, PriceSnapshot, SnipeAlert, CompletedTrade, init_db, get_session
import datetime

# Create an in-memory SQLite engine for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    async_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

@pytest.mark.asyncio
async def test_create_item(db_session: AsyncSession):
    item = Item(id="item-1", name="Test Item", rarity="Legendary")
    db_session.add(item)
    await db_session.commit()

    retrieved = await db_session.get(Item, "item-1")
    assert retrieved is not None
    assert retrieved.name == "Test Item"
    assert retrieved.rarity == "Legendary"

@pytest.mark.asyncio
async def test_create_price_snapshot(db_session: AsyncSession):
    item = Item(id="item-2", name="Test Item 2", rarity="Epic")
    db_session.add(item)
    await db_session.commit()

    snapshot = PriceSnapshot(item_id="item-2", price=150.0)
    db_session.add(snapshot)
    await db_session.commit()

    retrieved_snapshot = await db_session.get(PriceSnapshot, snapshot.id)
    assert retrieved_snapshot is not None
    assert retrieved_snapshot.item_id == "item-2"
    assert retrieved_snapshot.price == 150.0

@pytest.mark.asyncio
async def test_create_snipe_alert(db_session: AsyncSession):
    alert = SnipeAlert(item_id="item-3", price=50.0)
    db_session.add(alert)
    await db_session.commit()

    retrieved_alert = await db_session.get(SnipeAlert, alert.id)
    assert retrieved_alert is not None
    assert retrieved_alert.item_id == "item-3"
    assert retrieved_alert.price == 50.0
    assert retrieved_alert.is_notified is False

@pytest.mark.asyncio
async def test_create_completed_trade(db_session: AsyncSession):
    trade = CompletedTrade(item_id="item-4", price=200.0)
    db_session.add(trade)
    await db_session.commit()

    retrieved_trade = await db_session.get(CompletedTrade, trade.id)
    assert retrieved_trade is not None
    assert retrieved_trade.item_id == "item-4"
    assert retrieved_trade.price == 200.0

@pytest.mark.asyncio
async def test_get_session():
    # Test that get_session yields an AsyncSession
    async for session in get_session():
        assert isinstance(session, AsyncSession)
        break
