from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from datetime import datetime, timezone
import os

Base = declarative_base()

class Item(Base):
    __tablename__ = 'items'
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    rarity = Column(String, nullable=True)

class PriceSnapshot(Base):
    __tablename__ = 'price_snapshots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String, ForeignKey('items.id'), index=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SnipeAlert(Base):
    __tablename__ = 'snipe_alerts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String, ForeignKey('items.id'), index=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_notified = Column(Boolean, default=False)

class CompletedTrade(Base):
    __tablename__ = 'completed_trades'
    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String, ForeignKey('items.id'), index=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./market.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    async with engine.begin() as conn:
        # Create all tables (migrations can be handled by alembic later if needed, but simple create_all for now)
        await conn.run_sync(Base.metadata.create_all)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
