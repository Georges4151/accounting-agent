"""
税务相关模型
包含税务记录、申报截止日期和税务汇总
"""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Text, Date, DateTime, ForeignKey, Numeric, Boolean, JSON, func,
)
from .base import BaseModel


class TaxRecord(BaseModel):
    """税务记录表"""

    __tablename__ = "tax_records"

    tax_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="税种: 增值税/企业所得税/附加税/印花税/其他"
    )
    tax_period: Mapped[str] = mapped_column(
        String(7), nullable=False, comment="税务期间 YYYY-MM"
    )
    tax_period_type: Mapped[str] = mapped_column(
        String(20), default="monthly", nullable=False,
        comment="申报周期: monthly/quarterly/yearly"
    )
    taxable_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, nullable=False, comment="应纳税额基数"
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=0, nullable=False, comment="税率"
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, nullable=False, comment="应纳税额"
    )
    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, nullable=False, comment="已缴税额"
    )
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, nullable=False, comment="未缴税额"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="状态: pending/calculated/paid/overdue"
    )
    due_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="申报截止日期"
    )
    paid_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="实际缴纳日期"
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="备注"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="创建人ID"
    )
    calculation_detail: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="计算明细 JSON"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True, comment="所属账套ID"
    )


class TaxDeadline(BaseModel):
    """税务申报截止日期表"""

    __tablename__ = "tax_deadlines"

    tax_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="税种"
    )
    deadline_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="截止日期"
    )
    period: Mapped[str] = mapped_column(
        String(7), nullable=False, comment="所属期间 YYYY-MM"
    )
    reminder_days: Mapped[int] = mapped_column(
        Integer, default=7, nullable=False, comment="提前提醒天数"
    )
    is_reminded: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已提醒"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True, comment="所属账套ID"
    )


class TaxSummary(BaseModel):
    """税务汇总表（缓存）"""

    __tablename__ = "tax_summaries"

    period: Mapped[str] = mapped_column(
        String(7), nullable=False, comment="期间 YYYY-MM"
    )
    tax_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="税种"
    )
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, nullable=False, comment="总收入"
    )
    total_deductible: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, nullable=False, comment="可抵扣金额"
    )
    taxable_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, nullable=False, comment="应纳税基数"
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=0, nullable=False, comment="税率"
    )
    calculated_tax: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, nullable=False, comment="计算税额"
    )
    effective_tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), default=0, nullable=False, comment="实际税负率"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True, comment="所属账套ID"
    )