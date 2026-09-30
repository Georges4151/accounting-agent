"""
账套模型
包含账套主表和账套成员表
"""
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Boolean, Integer, Text, DateTime, ForeignKey, func,
)
from .base import BaseModel


class Book(BaseModel):
    """账套主表"""

    __tablename__ = "books"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="账套名称"
    )
    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="账套编码"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="描述"
    )
    company_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="公司全称"
    )
    tax_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="统一社会信用代码"
    )
    fiscal_year_start: Mapped[int] = mapped_column(
        Integer, default=1, comment="会计年度起始月"
    )
    fiscal_year_end: Mapped[int] = mapped_column(
        Integer, default=12, comment="会计年度结束月"
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="CNY", comment="币种"
    )
    decimal_places: Mapped[int] = mapped_column(
        Integer, default=2, comment="小数位数"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False,
        comment="状态: active/archived"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否默认账套"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="创建人ID"
    )

    # 关联关系
    members: Mapped[list["BookMember"]] = relationship(
        "BookMember", back_populates="book", cascade="all, delete-orphan", lazy="selectin"
    )


class BookMember(BaseModel):
    """账套成员表"""

    __tablename__ = "book_members"

    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, comment="账套ID"
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="用户ID"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="viewer",
        comment="账套内角色: admin/accountant/reviewer/viewer"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )

    # 关联关系
    book: Mapped["Book"] = relationship("Book", back_populates="members")