"""
工资管理模型
包含工资项目表和工资记录表
"""
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Numeric, ForeignKey, Text, JSON
from .base import BaseModel


class SalaryItem(BaseModel):
    """工资项目表"""

    __tablename__ = "salary_items"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="项目名称: 基本工资/加班费/社保"
    )
    item_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="项目类型: income/deduction"
    )
    formula: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="计算公式"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=0, comment="排序序号"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id"), nullable=True, comment="所属账套ID"
    )


class SalaryRecord(BaseModel):
    """工资记录表"""

    __tablename__ = "salary_records"

    employee_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="员工姓名"
    )
    employee_code: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="员工编号"
    )
    period: Mapped[str] = mapped_column(
        String(7), nullable=False, comment="工资期间: YYYY-MM"
    )
    salary_data: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="工资数据"
    )
    total_income: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, comment="收入合计"
    )
    total_deduction: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, comment="扣除合计"
    )
    net_salary: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, comment="实发工资"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="draft", comment="状态: draft/confirmed/paid"
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id"), nullable=True, comment="所属账套ID"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="创建人ID"
    )