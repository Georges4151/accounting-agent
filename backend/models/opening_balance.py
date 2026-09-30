"""
期初余额模型
用于管理各账套科目的期初余额
"""
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Numeric, ForeignKey, UniqueConstraint
from .base import BaseModel


class OpeningBalance(BaseModel):
    """期初余额表"""

    __tablename__ = "opening_balances"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, comment="账套ID"
    )
    account_code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="科目编码"
    )
    account_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="科目名称"
    )
    opening_debit: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="期初借方余额"
    )
    opening_credit: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="期初贷方余额"
    )
    fiscal_year: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="会计年度"
    )

    __table_args__ = (
        UniqueConstraint("book_id", "account_code", "fiscal_year", name="uq_book_account_year"),
    )