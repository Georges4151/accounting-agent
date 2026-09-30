"""
凭证相关模型
包含凭证主表、凭证分录和科目表
"""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Boolean, Integer, Text, Date, DateTime, ForeignKey, Numeric, JSON, func,
)
from .base import BaseModel


class Voucher(BaseModel):
    """凭证主表"""

    __tablename__ = "vouchers"

    voucher_type: Mapped[str] = mapped_column(
        String(10), default="记", nullable=False, comment="凭证字: 记/转/收/付"
    )
    voucher_no: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="凭证号"
    )
    voucher_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="凭证日期"
    )
    summary: Mapped[str] = mapped_column(
        Text, nullable=False, comment="摘要"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False,
        comment="状态: draft/submitted/reviewed/approved/posted"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id"), nullable=True, comment="所属账套ID"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="创建人ID"
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="审核人ID"
    )
    cashier_reviewed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, comment="出纳是否已复核"
    )
    cashier_reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="出纳复核人ID"
    )
    cashier_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="出纳复核时间"
    )
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, comment="审批人ID"
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="审批时间"
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="过账时间"
    )
    attachments: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="附件列表"
    )

    # 关联关系
    items: Mapped[list["VoucherItem"]] = relationship(
        "VoucherItem", back_populates="voucher", cascade="all, delete-orphan", lazy="selectin"
    )


class VoucherItem(BaseModel):
    """凭证分录明细"""

    __tablename__ = "voucher_items"

    voucher_id: Mapped[int] = mapped_column(
        ForeignKey("vouchers.id", ondelete="CASCADE"), nullable=False, comment="凭证ID"
    )
    account_code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="科目编码"
    )
    account_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="科目名称"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="分录描述"
    )
    debit_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, comment="借方金额"
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, comment="贷方金额"
    )
    cash_flow_tag: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="现金流量标记: operating/investing/financing"
    )
    auxiliary_accounting: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="辅助核算: {customer, supplier, department, project, employee}"
    )

    # 关联关系
    voucher: Mapped["Voucher"] = relationship("Voucher", back_populates="items")


class Account(BaseModel):
    """科目表"""

    __tablename__ = "accounts"

    account_code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="科目编码"
    )
    account_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="科目名称"
    )
    account_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="科目类型"
    )
    parent_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="上级科目编码"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id"), nullable=True, comment="所属账套ID"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    balance_direction: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="余额方向: debit/credit"
    )