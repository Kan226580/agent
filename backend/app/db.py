from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.settings import settings

# 创建异步数据库引擎
engine = create_async_engine(settings.admin.url)
# 创建异步会话工厂
AppSessionLocal = async_sessionmaker(
    expire_on_commit=False, autoflush=False, bind=engine
)


# 每个请求创建一个数据库 Session
async def get_db() -> AsyncIterator[AsyncSession]:
    async with AppSessionLocal() as session:
        yield session


# 给依赖起一个类型别名
DbSession = Annotated[AsyncSession, Depends(get_db)]
