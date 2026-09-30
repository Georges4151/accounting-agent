"""
数据库连接管理模块
使用 SQLAlchemy 2.0 异步引擎和会话
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from config.settings import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # 生产环境应设为 False
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,  # 连接前检查可用性
)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的异步依赖注入函数"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()