"""
固定资产模型
"""
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String, Integer, Numeric, ForeignKey, Date, Text, Boolean,
)
from .base import BaseModel


class FixedAsset(BaseModel):
    """固定资产卡片"""

    __tablename__ = "fixed_assets"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, comment="账套ID"
    )
    asset_code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="资产编码"
    )
    asset_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="资产名称"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="资产类别: 房屋建筑/机器设备/运输工具/电子设备/其他"
    )
    quantity: Mapped[int] = mapped_column(
        Integer, default=1, comment="数量"
    )
    unit: Mapped[str] = mapped_column(
        String(20), default="台", comment="计量单位"
    )
    purchase_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="购置日期"
    )
    original_value: Mapped[float] = mapped_column(
        Numeric(15, 2), nullable=False, comment="原值"
    )
    salvage_value: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="预计净残值"
    )
    useful_life_months: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="预计使用月数"
    )
    monthly_depreciation: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="月折旧额"
    )
    accumulated_depreciation: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="累计折旧"
    )
    net_value: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="净值"
    )
    depreciation_method: Mapped[str] = mapped_column(
        String(20), default="straight_line", comment="折旧方法: straight_line"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="in_use", comment="状态: in_use/fully_depreciated/scrapped/disposed"
    )
    account_code: Mapped[str] = mapped_column(
        String(50), default="1601", comment="对应科目编码"
    )
    dep_account_code: Mapped[str] = mapped_column(
        String(50), default="1602", comment="累计折旧科目编码"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="备注"
    )


class DepreciationRecord(BaseModel):
    """折旧记录"""

    __tablename__ = "depreciation_records"

    asset_id: Mapped[int] = mapped_column(
        ForeignKey("fixed_assets.id", ondelete="CASCADE"), nullable=False, comment="资产ID"
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, comment="账套ID"
    )
    period: Mapped[str] = mapped_column(
        String(7), nullable=False, comment="折旧期间 YYYY-MM"
    )
    depreciation_amount: Mapped[float] = mapped_column(
        Numeric(15, 2), nullable=False, comment="本期折旧额"
    )
    accumulated_before: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="折旧前累计折旧"
    )
    accumulated_after: Mapped[float] = mapped_column(
        Numeric(15, 2), default=0, comment="折旧后累计折旧"
    )
    voucher_id: Mapped[int | None] = mapped_column(
        ForeignKey("vouchers.id"), nullable=True, comment="关联凭证ID"
    )