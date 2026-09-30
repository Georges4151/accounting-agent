"""
预算管理相关模型
包含预算表、预算预警表和预算备注表
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Integer, Text, DateTime, ForeignKey, Numeric, Boolean, func,
)
from .base import BaseModel


class Budget(BaseModel):
    """预算表"""

    __tablename__ = "budgets"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="预算名称"
    )
    year: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="预算年份"
    )
    month: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, comment="预算月份, 0=年度预算"
    )
    account_code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="科目编码"
    )
    account_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="科目名称"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id"), nullable=True, comment="所属账套ID"
    )
    budget_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="预算金额"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False, comment="状态: active/closed"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="创建人ID"
    )

    # 关联关系
    alerts: Mapped[list["BudgetAlert"]] = relationship(
        "BudgetAlert", back_populates="budget", cascade="all, delete-orphan", lazy="selectin"
    )
    notes: Mapped[list["BudgetNote"]] = relationship(
        "BudgetNote", back_populates="budget", cascade="all, delete-orphan", lazy="selectin"
    )


class BudgetAlert(BaseModel):
    """预算预警表"""

    __tablename__ = "budget_alerts"

    budget_id: Mapped[int] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, comment="预算ID"
    )
    alert_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="预警类型: overspend/threshold"
    )
    threshold_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, comment="触发阈值百分比"
    )
    is_triggered: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已触发"
    )
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="触发时间"
    )
    notified: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已通知"
    )

    # 关联关系
    budget: Mapped["Budget"] = relationship("Budget", back_populates="alerts")


class BudgetNote(BaseModel):
    """预算备注表"""

    __tablename__ = "budget_notes"

    budget_id: Mapped[int] = mapped_column(
        ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, comment="预算ID"
    )
    note_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="备注内容"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="创建人ID"
    )

    # 关联关系
    budget: Mapped["Budget"] = relationship("Budget", back_populates="notes")