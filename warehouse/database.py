from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlmodel import SQLModel
from contextlib import asynccontextmanager
import os
from warehouse.utils import get_base_path

# Using a relative path for the database so it works on USB
# We use get_base_path() to ensure it's relative to the executable when frozen
db_path = os.path.join(get_base_path(), "warehouse.db")
DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

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
            
        # Migration for min_stock column
        try:
            await conn.execute(text("ALTER TABLE material ADD COLUMN min_stock INTEGER DEFAULT 0"))
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
