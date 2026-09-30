"""
对话记忆模型
存储从对话中提取的持久化用户记忆
"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from models.base import BaseModel


class ConversationMemory(BaseModel):
    """对话记忆表：存储 AI 从对话中学到的用户偏好、知识和上下文"""

    __tablename__ = "conversation_memories"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, comment="用户ID"
    )
    memory_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="context_hint",
        comment="记忆类型: user_preference/accounting_knowledge/context_hint"
    )
    memory_key: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="记忆关键词"
    )
    memory_value: Mapped[str] = mapped_column(
        Text, nullable=False, comment="记忆内容"
    )
    importance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, comment="重要性 1-5"
    )
    last_recalled_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后召回时间"
    )