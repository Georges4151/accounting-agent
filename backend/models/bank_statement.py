"""
银行对账单模型
"""
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Numeric, ForeignKey, Boolean, Date, Text
from .base import BaseModel


class BankStatement(BaseModel):
    """银行对账单"""

    __tablename__ = "bank_statements"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, comment="账套ID"
    )
    bank_account: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="银行账号"
    )
    transaction_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="交易日期"
    )
    description: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="交易摘要"
    )
    debit_amount: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="借方金额(银行收入)"
    )
    credit_amount: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="贷方金额(银行支出)"
    )
    balance: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="余额"
    )
    matched_voucher_id: Mapped[int | None] = mapped_column(
        ForeignKey("vouchers.id"), nullable=True, comment="匹配的凭证ID"
    )
    matched_voucher_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("voucher_items.id"), nullable=True, comment="匹配的凭证分录ID"
    )
    match_status: Mapped[str] = mapped_column(
        String(20), default="unmatched", comment="匹配状态: matched/unmatched/partial"
    )
    match_confidence: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0, comment="匹配置信度"
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="备注"
    )