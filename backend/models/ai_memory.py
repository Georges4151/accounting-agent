"""
AI 跨会话记忆模型
存储 AI 从对话中提取的用户偏好、知识和上下文信息
"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from models.base import BaseModel


class AIMemory(BaseModel):
    """AI 记忆表：存储用户偏好、知识和上下文"""

    __tablename__ = "ai_memories"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, comment="用户ID"
    )
    memory_key: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="记忆关键词"
    )
    memory_value: Mapped[str] = mapped_column(
        Text, nullable=False, comment="记忆内容"
    )
    memory_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="context",
        comment="记忆类型: preference/knowledge/context"
    )
    importance: Mapped[float] = mapped_column(
        Float, nullable=False, default=5.0, comment="重要性 0-10"
    )
    access_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="访问次数"
    )
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime, nullable=True, comment="最后访问时间"
    )