"""
发票管理 API
提供发票上传、AI 识别、查询、关联凭证等功能
"""
import logging
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth.middleware import get_current_user
from auth.book_context import get_current_book
from models.user import User
from models.invoice import Invoice
from models.book import Book
from services.invoice_service import invoice_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/invoices", tags=["发票管理"])

# 上传文件大小限制 20MB
MAX_UPLOAD_SIZE = 20 * 1024 * 1024


# ========== Pydantic 模型 ==========

class InvoiceItemResponse(BaseModel):
    name: str = ""
    quantity: float = 0
    price: float = 0
    amount: float = 0


class InvoiceResponse(BaseModel):
    id: int
    doc_type: str = "invoice"
    invoice_type: str = ""
    invoice_number: str = ""
    invoice_code: str = ""
    invoice_date: Optional[str] = None
    amount: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    seller_name: str = ""
    seller_tax_id: str = ""
    buyer_name: str = ""
    buyer_tax_id: str = ""
    items: Optional[list] = None
    extracted_text: Optional[str] = None
    details: Optional[dict] = None
    _parse_error: Optional[str] = None
    image_available: bool = False
    status: str = "pending"
    voucher_id: Optional[int] = None
    remark: str = ""
    created_at: Optional[str] = None


class InvoiceUpdateRequest(BaseModel):
    """手动编辑发票信息"""
    invoice_type: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_code: Optional[str] = None
    invoice_date: Optional[str] = None
    amount: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    seller_name: Optional[str] = None
    seller_tax_id: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_tax_id: Optional[str] = None
    items: Optional[list] = None
    remark: Optional[str] = None


class InvoiceListResponse(BaseModel):
    invoices: List[InvoiceResponse]
    total: int
    page: int
    page_size: int


# ========== 辅助函数 ==========

def _invoice_to_response(inv: Invoice) -> InvoiceResponse:
    """将 Invoice ORM 对象转为响应模型"""
    return InvoiceResponse(
        id=inv.id,
        doc_type=inv.doc_type or "invoice",
        invoice_type=inv.invoice_type or "",
        invoice_number=inv.invoice_number or "",
        invoice_code=inv.invoice_code or "",
        invoice_date=inv.invoice_date.isoformat() if inv.invoice_date else None,
        amount=float(inv.amount) if inv.amount else None,
        tax_amount=float(inv.tax_amount) if inv.tax_amount else None,
        total_amount=float(inv.total_amount) if inv.total_amount else None,
        seller_name=inv.seller_name or "",
        seller_tax_id=inv.seller_tax_id or "",
        buyer_name=inv.buyer_name or "",
        buyer_tax_id=inv.buyer_tax_id or "",
        items=inv.items,
        extracted_text=inv.extracted_text,
        details=inv.details,
        _parse_error=getattr(inv, '_parse_error', None),
        image_available=bool(inv.original_image_path),
        status=inv.status or "pending",
        voucher_id=inv.voucher_id,
        remark=inv.remark or "",
        created_at=inv.created_at.isoformat() if inv.created_at else None,
    )


# ========== API 路由 ==========

@router.post("/upload", summary="上传票据图片")
async def upload_invoice(
    file: UploadFile = File(...),
    doc_type: str = Query("invoice", description="票据类型: invoice/bank_receipt/expense_report"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """上传票据图片，保存原始票据，支持发票/银行回单/费用报销单"""
    # 校验 doc_type
    if doc_type not in ("invoice", "bank_receipt", "expense_report"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的票据类型: {doc_type}，支持: invoice, bank_receipt, expense_report",
        )
    # 校验文件类型
    ext = Path(file.filename or "unknown").suffix.lower()
    if ext not in invoice_service.SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的图片格式: {ext}，支持: {', '.join(invoice_service.SUPPORTED_EXTENSIONS)}",
        )

    # 校验文件大小
    file_data = await file.read()
    if len(file_data) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件大小超过限制 ({MAX_UPLOAD_SIZE // 1024 // 1024}MB)",
        )

    # 保存文件
    try:
        image_path = invoice_service.save_uploaded_file(file_data, file.filename or "invoice")
    except Exception as e:
        logger.error(f"保存发票图片失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="保存图片失败")

    # 创建发票记录
    invoice = Invoice(
        user_id=current_user.id,
        book_id=current_book.id,
        doc_type=doc_type,
        original_image_path=image_path,
        status="pending",
    )
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    logger.info(f"票据上传成功: id={invoice.id}, doc_type={doc_type}, path={image_path}")

    return {
        "id": invoice.id,
        "doc_type": doc_type,
        "message": "票据上传成功",
        "image_path": image_path,
    }


@router.post("/{invoice_id}/recognize", summary="AI 识别票据")
async def recognize_invoice(
    invoice_id: int,
    doc_type: str = Query("invoice", description="票据类型: invoice/bank_receipt/expense_report"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """使用 AI 识别票据内容，支持发票/银行回单/费用报销单"""
    # 校验 doc_type
    if doc_type not in ("invoice", "bank_receipt", "expense_report"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的票据类型: {doc_type}，支持: invoice, bank_receipt, expense_report",
        )

    # 查询发票
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="票据不存在")

    if not invoice.original_image_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="票据图片不存在")

    # 调用 AI 识别
    full_path = Path(invoice.original_image_path)
    if not full_path.is_absolute():
        full_path = Path.cwd() / full_path

    if not full_path.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="票据图片文件不存在，请重新上传")

    try:
        recognized = await invoice_service.recognize_document(str(full_path), doc_type)
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    # 记录识别使用的 doc_type
    invoice.doc_type = doc_type

    if doc_type == "bank_receipt":
        # 银行回单：识别结果存入 details 字段
        invoice.details = recognized
        invoice.extracted_text = recognized.get("extracted_raw_text", "")
        invoice.invoice_type = recognized.get("receipt_type", "")
        invoice.invoice_number = recognized.get("transaction_id", "")

        inv_date = recognized.get("transaction_date", "")
        if inv_date:
            try:
                invoice.invoice_date = date.fromisoformat(inv_date)
            except (ValueError, TypeError):
                pass

        try:
            invoice.total_amount = Decimal(str(recognized.get("amount", 0)))
        except (ValueError, TypeError, Exception):
            pass

        invoice.seller_name = recognized.get("payer_name", "")
        invoice.buyer_name = recognized.get("payee_name", "")

    elif doc_type == "expense_report":
        # 费用报销单：识别结果存入 details 字段
        invoice.details = recognized
        invoice.extracted_text = recognized.get("extracted_raw_text", "")
        invoice.invoice_type = "费用报销单"
        invoice.invoice_number = recognized.get("report_no", "")

        inv_date = recognized.get("report_date", "")
        if inv_date:
            try:
                invoice.invoice_date = date.fromisoformat(inv_date)
            except (ValueError, TypeError):
                pass

        try:
            invoice.total_amount = Decimal(str(recognized.get("total_amount", 0)))
        except (ValueError, TypeError, Exception):
            pass

        invoice.seller_name = recognized.get("applicant", "")
        invoice.buyer_name = recognized.get("department", "")
        invoice.items = recognized.get("items", [])
        invoice.remark = recognized.get("reason", "")

    else:
        # 发票：使用原有逻辑
        invoice.invoice_type = recognized.get("invoice_type", "")
        invoice.invoice_number = recognized.get("invoice_number", "")
        invoice.invoice_code = recognized.get("invoice_code", "")

        inv_date = recognized.get("invoice_date", "")
        if inv_date:
            try:
                invoice.invoice_date = date.fromisoformat(inv_date)
            except (ValueError, TypeError):
                pass

        try:
            invoice.amount = Decimal(str(recognized.get("amount", 0)))
            invoice.tax_amount = Decimal(str(recognized.get("tax_amount", 0)))
            invoice.total_amount = Decimal(str(recognized.get("total_amount", 0)))
        except (ValueError, TypeError, Exception):
            pass

        invoice.seller_name = recognized.get("seller_name", "")
        invoice.seller_tax_id = recognized.get("seller_tax_id", "")
        invoice.buyer_name = recognized.get("buyer_name", "")
        invoice.buyer_tax_id = recognized.get("buyer_tax_id", "")
        invoice.items = recognized.get("items", [])
        invoice.extracted_text = recognized.get("extracted_raw_text", "")

    invoice.status = "recognized"

    # 检查同一账套内是否存在相同编号的票据（仅发票类型检查编号）
    if doc_type == "invoice" and invoice.invoice_number:
        dup_result = await db.execute(
            select(Invoice).where(
                Invoice.invoice_number == invoice.invoice_number,
                Invoice.book_id == current_book.id,
                Invoice.id != invoice.id
            ).limit(1)
        )
        if dup_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"发票编号 {invoice.invoice_number} 已存在，请勿重复录入",
            )

    await db.commit()
    await db.refresh(invoice)

    # 透传解析错误（非DB字段，需在refresh后设置）
    invoice._parse_error = recognized.get("_parse_error", None)

    doc_type_labels = {"invoice": "发票", "bank_receipt": "银行回单", "expense_report": "费用报销单"}
    logger.info(f"{doc_type_labels.get(doc_type, '票据')}识别完成: id={invoice_id}")

    return {
        "message": f"{doc_type_labels.get(doc_type, '票据')}识别完成",
        "invoice": _invoice_to_response(invoice),
    }


@router.get("", summary="发票列表")
async def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="按状态筛选: pending/recognized/verified/archived"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取发票列表，支持分页和状态筛选"""
    query = select(Invoice).where(Invoice.user_id == current_user.id)
    count_query = select(func.count(Invoice.id)).where(Invoice.user_id == current_user.id)

    if status:
        query = query.where(Invoice.status == status)
        count_query = count_query.where(Invoice.status == status)

    result = await db.execute(count_query)
    total = result.scalar() or 0

    query = query.order_by(desc(Invoice.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    invoices = result.scalars().all()

    return InvoiceListResponse(
        invoices=[_invoice_to_response(inv) for inv in invoices],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{invoice_id}", summary="发票详情")
async def get_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取发票详情"""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发票不存在")

    return _invoice_to_response(invoice)


@router.get("/{invoice_id}/image", summary="获取发票原始图片")
async def get_invoice_image(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取发票原始图片文件（用于审计查看）"""
    from fastapi.responses import FileResponse

    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发票不存在")

    if not invoice.original_image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发票图片不存在")

    full_path = Path(invoice.original_image_path)
    if not full_path.is_absolute():
        full_path = Path.cwd() / full_path

    if not full_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片文件不存在")

    return FileResponse(str(full_path))


@router.put("/{invoice_id}", summary="编辑发票信息")
async def update_invoice(
    invoice_id: int,
    data: InvoiceUpdateRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """手动编辑发票信息（AI识别不准确时）"""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发票不存在")

    if data.invoice_type is not None:
        invoice.invoice_type = data.invoice_type
    if data.invoice_number is not None:
        invoice.invoice_number = data.invoice_number
    if data.invoice_code is not None:
        invoice.invoice_code = data.invoice_code
    if data.invoice_date is not None:
        try:
            invoice.invoice_date = date.fromisoformat(data.invoice_date)
        except (ValueError, TypeError):
            pass
    if data.amount is not None:
        invoice.amount = Decimal(str(data.amount))
    if data.tax_amount is not None:
        invoice.tax_amount = Decimal(str(data.tax_amount))
    if data.total_amount is not None:
        invoice.total_amount = Decimal(str(data.total_amount))
    if data.seller_name is not None:
        invoice.seller_name = data.seller_name
    if data.seller_tax_id is not None:
        invoice.seller_tax_id = data.seller_tax_id
    if data.buyer_name is not None:
        invoice.buyer_name = data.buyer_name
    if data.buyer_tax_id is not None:
        invoice.buyer_tax_id = data.buyer_tax_id
    if data.items is not None:
        invoice.items = data.items
    if data.remark is not None:
        invoice.remark = data.remark

    # 检查同一账套内是否存在相同编号的发票
    if invoice.invoice_number:
        dup_result = await db.execute(
            select(Invoice).where(
                Invoice.invoice_number == invoice.invoice_number,
                Invoice.book_id == current_book.id,
                Invoice.id != invoice.id
            ).limit(1)
        )
        if dup_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"发票编号 {invoice.invoice_number} 已存在，请勿重复录入",
            )

    invoice.status = "verified"
    await db.commit()
    await db.refresh(invoice)

    return {
        "message": "发票信息已更新",
        "invoice": _invoice_to_response(invoice),
    }


@router.delete("/{invoice_id}", summary="删除发票")
async def delete_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除发票记录及图片文件"""
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发票不存在")

    if invoice.voucher_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该发票已关联凭证，请先解除凭证关联",
        )

    # 删除图片文件
    if invoice.original_image_path:
        try:
            full_path = Path(invoice.original_image_path)
            if not full_path.is_absolute():
                full_path = Path.cwd() / full_path
            if full_path.exists():
                full_path.unlink()
        except Exception as e:
            logger.warning(f"删除发票图片失败: {e}")

    await db.delete(invoice)
    await db.commit()

    return {"message": "发票已删除"}


@router.post("/{invoice_id}/generate-voucher", summary="从发票生成凭证")
async def generate_voucher_from_invoice(
    invoice_id: int,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """
    从已识别的发票自动生成凭证。
    需要先完成 AI 识别或手动填写发票信息。
    """
    from models.voucher import Voucher, VoucherItem, Account
    from datetime import date as date_type

    today = date_type.today()

    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id, Invoice.user_id == current_user.id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发票不存在")

    if invoice.status == "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先完成发票识别")

    if invoice.voucher_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该发票已生成凭证")

    if not invoice.total_amount or invoice.total_amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="发票金额无效")

    # 检查同一账套内是否存在相同编号的发票（友好提示，不阻止生成）
    if invoice.invoice_number:
        dup_result = await db.execute(
            select(Invoice).where(
                Invoice.invoice_number == invoice.invoice_number,
                Invoice.book_id == current_book.id,
                Invoice.id != invoice.id
            ).limit(1)
        )
        duplicate_invoice = dup_result.scalar_one_or_none()
        if duplicate_invoice:
            logger.warning(
                f"账套 {current_book.name} 内存在相同编号的发票: "
                f"#{invoice.invoice_number}（当前发票ID={invoice.id}，已存在发票ID={duplicate_invoice.id}）"
            )

    # 生成凭证号（使用时间戳后缀避免重复）
    today_str = today.strftime('%Y%m%d')
    # 查找今天最大的凭证号后缀
    result = await db.execute(
        select(Voucher.voucher_no).where(
            Voucher.voucher_no.like(f"INV-{today_str}-%")
        ).order_by(Voucher.voucher_no.desc()).limit(1)
    )
    last_no = result.scalar_one_or_none()
    if last_no:
        try:
            suffix = int(last_no.split("-")[-1]) + 1
        except (ValueError, IndexError):
            suffix = 1
    else:
        suffix = 1
    voucher_no = f"INV-{today_str}-{suffix:03d}"

    # 查找或创建科目（按当前账套过滤）
    # 默认借方：管理费用-办公费
    result = await db.execute(
        select(Account).where(
            Account.account_code == "6602",
            (Account.book_id == current_book.id) | (Account.book_id.is_(None))
        ).limit(1)
    )
    debit_account = result.scalar_one_or_none()
    if not debit_account:
        debit_account = Account(
            account_code="6602", account_name="管理费用",
            account_type="expense", balance_direction="debit",
            book_id=current_book.id
        )
        db.add(debit_account)
        await db.flush()

    # 默认贷方：银行存款
    result = await db.execute(
        select(Account).where(
            Account.account_code == "1002",
            (Account.book_id == current_book.id) | (Account.book_id.is_(None))
        ).limit(1)
    )
    credit_account = result.scalar_one_or_none()
    if not credit_account:
        credit_account = Account(
            account_code="1002", account_name="银行存款",
            account_type="asset", balance_direction="debit",
            book_id=current_book.id
        )
        db.add(credit_account)
        await db.flush()

    # 创建凭证
    summary = f"发票报销 - {invoice.seller_name or '供应商'} {invoice.invoice_number or ''}"
    if invoice.invoice_date:
        voucher_date = invoice.invoice_date
    else:
        voucher_date = today

    voucher = Voucher(
        voucher_no=voucher_no,
        voucher_date=voucher_date,
        summary=summary,
        status="draft",
        created_by=current_user.id,
        book_id=current_book.id,
    )
    db.add(voucher)
    await db.flush()

    # 借方分录
    debit_item = VoucherItem(
        voucher_id=voucher.id,
        account_code=debit_account.account_code,
        account_name=debit_account.account_name,
        description=summary,
        debit_amount=invoice.amount or invoice.total_amount,
        credit_amount=Decimal("0"),
    )
    db.add(debit_item)

    # 贷方分录
    credit_item = VoucherItem(
        voucher_id=voucher.id,
        account_code=credit_account.account_code,
        account_name=credit_account.account_name,
        description=summary,
        debit_amount=Decimal("0"),
        credit_amount=invoice.amount or invoice.total_amount,
    )
    db.add(credit_item)

    # 关联发票到凭证
    invoice.voucher_id = voucher.id
    invoice.status = "archived"

    await db.commit()
    await db.refresh(voucher)

    logger.info(f"从发票生成凭证: invoice_id={invoice_id}, voucher_no={voucher_no}")

    return {
        "message": "凭证生成成功",
        "voucher_id": voucher.id,
        "voucher_no": voucher_no,
    }