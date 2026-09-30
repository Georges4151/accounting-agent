"""
对话和消息数据模型
"""
from datetime import datetime
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models.base import BaseModel


class Conversation(BaseModel):
    """对话会话"""
    __tablename__ = "conversations"

    title: Mapped[str] = mapped_column(String(200), default="新对话")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, comment="对话摘要")
    topic_tags: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="主题标签（逗号分隔）"
    )
    memory_keywords: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="提取的关键词/主题列表"
    )
    memory_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI自动生成的对话摘要"
    )
    last_accessed: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后访问时间"
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation",
        cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(BaseModel):
    """对话消息"""
    __tablename__ = "messages"

    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )