"""
多币种管理模型
包含币种表和汇率表
"""
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Date, Numeric, ForeignKey
from .base import BaseModel


class Currency(BaseModel):
    """币种表"""

    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(
        String(10), unique=True, nullable=False, comment="币种代码: CNY/USD/EUR"
    )
    name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="币种名称"
    )
    symbol: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="符号: ¥/$"
    )
    is_base: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否本位币"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="状态: active/inactive"
    )


class ExchangeRate(BaseModel):
    """汇率表"""

    __tablename__ = "exchange_rates"

    currency_code: Mapped[str] = mapped_column(
        String(10), ForeignKey("currencies.code"), nullable=False, comment="币种代码"
    )
    rate_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="汇率日期"
    )
    rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 8), nullable=False, comment="汇率: 1外币=?本位币"
    )
    rate_type: Mapped[str] = mapped_column(
        String(20), default="middle", comment="汇率类型: middle/buy/sell"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id"), nullable=True, comment="所属账套ID"
    )