"""通知模型"""
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, ForeignKey, Text, Boolean, DateTime
from .base import BaseModel


class Notification(BaseModel):
    """系统通知"""
    __tablename__ = "notifications"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    book_id: Mapped[int | None] = mapped_column(ForeignKey("books.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="info", comment="info/warning/success/error")
    category: Mapped[str] = mapped_column(String(30), default="system", comment="system/voucher/invoice/approval/tax")
    link: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="跳转链接")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)