from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlmodel import SQLModel
from contextlib import asynccontextmanager

# Using a relative path for the database so it works on USB
DATABASE_URL = "sqlite+aiosqlite:///warehouse.db"

engine = create_async_engine(DATABASE_URL, echo=False, future=True)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        
        # Simple migration for is_efficient column
        try:
            await conn.execute(text("ALTER TABLE material ADD COLUMN is_efficient BOOLEAN DEFAULT 1"))
        except Exception:
            # Column likely exists
            pass

@asynccontextmanager
async def get_session():
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
