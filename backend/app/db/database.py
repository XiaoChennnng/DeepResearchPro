"""
数据库连接和会话管理
小陈说：数据库是应用的心脏，别tm乱搞
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import os

from app.core.config import settings
from app.core.logging import logger


class Base(DeclarativeBase):
    """ORM基类，所有模型都继承这个"""
    pass


# 确保数据目录存在
os.makedirs("data", exist_ok=True)

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # Debug模式下打印SQL
)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """
    获取数据库会话
    用于依赖注入，每次请求一个新会话
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    初始化数据库，创建所有表
    小陈我在启动时调用这个
    """
    # 导入所有模型，确保它们被注册
    from app.db import models  # noqa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("数据库表创建完成")
