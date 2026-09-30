"""
会计期间模型
用于管理结账/反结账的会计期间状态
"""
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, ForeignKey
from .base import BaseModel


class AccountingPeriod(BaseModel):
    """会计期间表"""

    __tablename__ = "accounting_periods"

    book_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("books.id"), nullable=False, comment="所属账套ID"
    )
    period_year: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="会计年度"
    )
    period_month: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="会计月份 1-12"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False, comment="状态: open/closed"
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="结账时间"
    )
    closed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="结账人ID"
    )
    reopened_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="反结账时间"
    )
    reopened_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, comment="反结账人ID"
    )