from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DatabaseSettings

database_settings = DatabaseSettings()
engine = create_async_engine(database_settings.DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
