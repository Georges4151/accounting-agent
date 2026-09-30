"""
凭证模板模型
包含凭证模板主表和模板分录表
"""
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Boolean, Integer, Text, ForeignKey, Numeric,
)
from .base import BaseModel


class VoucherTemplate(BaseModel):
    """凭证模板主表"""

    __tablename__ = "voucher_templates"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="模板名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="模板描述"
    )
    category: Mapped[str] = mapped_column(
        String(20), nullable=False, default="其他", comment="分类: 收入/支出/转账/其他"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否系统默认模板"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id"), nullable=True, comment="所属账套ID"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="创建人ID"
    )

    # 关联关系
    items: Mapped[list["VoucherTemplateItem"]] = relationship(
        "VoucherTemplateItem", back_populates="template", cascade="all, delete-orphan", lazy="selectin"
    )


class VoucherTemplateItem(BaseModel):
    """凭证模板分录明细"""

    __tablename__ = "voucher_template_items"

    template_id: Mapped[int] = mapped_column(
        ForeignKey("voucher_templates.id", ondelete="CASCADE"), nullable=False, comment="模板ID"
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
        Numeric(15, 2), default=0, comment="借方金额（可为0作占位）"
    )
    credit_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, comment="贷方金额（可为0作占位）"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序"
    )

    # 关联关系
    template: Mapped["VoucherTemplate"] = relationship("VoucherTemplate", back_populates="items")