"""
发票模型
用于存储发票识别结果和原始票据图片
"""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Boolean, Integer, Text, Date, DateTime, ForeignKey, Numeric, JSON, func,
)
from .base import BaseModel


class Invoice(BaseModel):
    """发票识别记录表"""

    __tablename__ = "invoices"

    # 用户关联
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, comment="上传用户ID"
    )
    book_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("books.id"), nullable=True, comment="所属账套ID"
    )

    # 票据类型标识
    doc_type: Mapped[str] = mapped_column(
        String(20), default="invoice", comment="票据类型: invoice/bank_receipt/expense_report"
    )

    # 原始票据信息
    invoice_type: Mapped[str] = mapped_column(
        String(30), default="", comment="发票类型：增值税专用发票/增值税普通发票/电子发票/其他"
    )
    invoice_number: Mapped[str] = mapped_column(
        String(50), default="", index=True, comment="发票号码"
    )
    invoice_code: Mapped[str] = mapped_column(
        String(50), default="", comment="发票代码"
    )
    invoice_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="开票日期"
    )

    # 金额信息
    amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True, comment="金额（不含税）"
    )
    tax_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True, comment="税额"
    )
    total_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2), nullable=True, comment="价税合计"
    )

    # 交易双方
    seller_name: Mapped[str] = mapped_column(
        String(200), default="", comment="销售方名称"
    )
    seller_tax_id: Mapped[str] = mapped_column(
        String(50), default="", comment="销售方纳税人识别号"
    )
    buyer_name: Mapped[str] = mapped_column(
        String(200), default="", comment="购买方名称"
    )
    buyer_tax_id: Mapped[str] = mapped_column(
        String(50), default="", comment="购买方纳税人识别号"
    )

    # 明细信息（JSON格式存储）
    items: Mapped[str | None] = mapped_column(
        JSON, nullable=True, comment="发票明细 [{name, quantity, price, amount}]"
    )

    # 原始识别文本
    extracted_text: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI 识别的原始文本"
    )

    # 详情（银行回单/报销单等非发票类型的识别结果，JSON格式）
    details: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="票据详情（银行回单/报销单等，JSON格式）"
    )

    # 原始票据图片
    original_image_path: Mapped[str] = mapped_column(
        String(500), default="", comment="原始图片路径"
    )
    thumbnail_path: Mapped[str] = mapped_column(
        String(500), default="", comment="缩略图路径"
    )

    # 状态与关联
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True,
        comment="状态: pending/recognized/verified/archived"
    )
    voucher_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vouchers.id"), nullable=True, comment="关联的凭证ID"
    )
    remark: Mapped[str] = mapped_column(
        String(500), default="", comment="备注"
    )