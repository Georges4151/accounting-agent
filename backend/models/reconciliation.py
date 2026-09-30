"""
往来管理模型
包括应收应付核销表
"""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Numeric, Date, Text, ForeignKey, DateTime, func
from .base import BaseModel


class Reconciliation(BaseModel):
    """应收应付核销表"""

    __tablename__ = "reconciliations"

    reconciliation_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="核销类型: ar-应收, ap-应付"
    )
    party_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="往来方类型: customer-客户, supplier-供应商"
    )
    party_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="客户/供应商名称"
    )
    party_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="客户/供应商编码"
    )
    voucher_id: Mapped[int | None] = mapped_column(
        ForeignKey("vouchers.id"), nullable=True, comment="关联凭证ID"
    )
    voucher_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("voucher_items.id"), nullable=True, comment="关联凭证分录ID"
    )
    invoice_no: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="发票号"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, comment="金额"
    )
    reconciled_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), comment="已核销金额"
    )
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=Decimal("0"), comment="未核销金额"
    )
    due_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="到期日"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", comment="状态: pending/partial/reconciled"
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="备注"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id"), nullable=True, comment="账套ID"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="创建人ID"
    )