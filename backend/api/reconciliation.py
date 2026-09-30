"""
往来管理 API 路由
提供应收应付核销、账龄分析、对账单等功能
"""
import logging
from typing import Optional, List
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.reconciliation import Reconciliation
from auth.middleware import get_current_user, require_permission
from auth.book_context import get_current_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reconciliations", tags=["往来管理"])


# ========== 请求/响应模型 ==========

class ReconciliationCreate(BaseModel):
    """创建核销记录请求体"""
    reconciliation_type: str = Field(..., description="核销类型: ar/ap")
    party_type: str = Field(..., description="往来方类型: customer/supplier")
    party_name: str = Field(..., description="客户/供应商名称")
    party_code: Optional[str] = Field(None, description="客户/供应商编码")
    voucher_id: Optional[int] = Field(None, description="关联凭证ID")
    voucher_item_id: Optional[int] = Field(None, description="关联凭证分录ID")
    invoice_no: Optional[str] = Field(None, description="发票号")
    amount: float = Field(..., gt=0, description="金额")
    due_date: Optional[str] = Field(None, description="到期日")
    notes: Optional[str] = Field(None, description="备注")


class ReconciliationUpdate(BaseModel):
    """更新核销记录请求体"""
    reconciliation_type: Optional[str] = Field(None, description="核销类型")
    party_type: Optional[str] = Field(None, description="往来方类型")
    party_name: Optional[str] = Field(None, description="客户/供应商名称")
    party_code: Optional[str] = Field(None, description="客户/供应商编码")
    invoice_no: Optional[str] = Field(None, description="发票号")
    amount: Optional[float] = Field(None, gt=0, description="金额")
    due_date: Optional[str] = Field(None, description="到期日")
    notes: Optional[str] = Field(None, description="备注")


class WriteOffRequest(BaseModel):
    """核销请求体"""
    write_off_amount: float = Field(..., gt=0, description="本次核销金额")


class BatchWriteOffRequest(BaseModel):
    """批量核销请求体"""
    ids: List[int] = Field(..., description="核销记录ID列表")
    write_off_amounts: Optional[dict] = Field(None, description="各ID对应核销金额，不传则全额核销")


class ReconciliationResponse(BaseModel):
    """核销记录响应体"""
    id: int
    reconciliation_type: str
    party_type: str
    party_name: str
    party_code: Optional[str] = None
    voucher_id: Optional[int] = None
    voucher_item_id: Optional[int] = None
    invoice_no: Optional[str] = None
    amount: float
    reconciled_amount: float
    remaining_amount: float
    due_date: Optional[str] = None
    status: str
    notes: Optional[str] = None
    book_id: Optional[int] = None
    created_by: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """分页响应"""
    items: list
    total: int
    page: int
    page_size: int


class AgingItem(BaseModel):
    """账龄分析项"""
    party_type: str
    party_name: str
    party_code: Optional[str] = None
    amount: float
    aging_0_30: float = 0
    aging_30_60: float = 0
    aging_60_90: float = 0
    aging_90_180: float = 0
    aging_180_365: float = 0
    aging_365_plus: float = 0


class AgingSummaryItem(BaseModel):
    """账龄汇总区间"""
    label: str
    amount: float
    percentage: float = 0


class AgingResponse(BaseModel):
    """账龄分析响应"""
    items: List[AgingItem] = []
    summary: List[AgingSummaryItem] = []


class StatementItem(BaseModel):
    """对账单明细项"""
    date: str
    document_type: str = ""
    document_no: str = ""
    description: str = ""
    debit_amount: float = 0
    credit_amount: float = 0
    balance: float = 0


class StatementResponse(BaseModel):
    """对账单响应"""
    party_type: str
    party_name: str
    party_code: Optional[str] = None
    start_date: str
    end_date: str
    opening_balance: float = 0
    items: List[StatementItem] = []
    total_debit: float = 0
    total_credit: float = 0
    closing_balance: float = 0


# ========== 辅助函数 ==========

def _to_aging_bucket(due_date: date, today: date) -> str:
    """计算账龄区间"""
    if due_date is None:
        return "aging_365_plus"
    diff = (today - due_date).days
    if diff <= 0:
        return "aging_0_30"
    elif diff <= 30:
        return "aging_0_30"
    elif diff <= 60:
        return "aging_30_60"
    elif diff <= 90:
        return "aging_60_90"
    elif diff <= 180:
        return "aging_90_180"
    elif diff <= 365:
        return "aging_180_365"
    else:
        return "aging_365_plus"


def _build_response(r: Reconciliation) -> ReconciliationResponse:
    return ReconciliationResponse(
        id=r.id,
        reconciliation_type=r.reconciliation_type,
        party_type=r.party_type,
        party_name=r.party_name,
        party_code=r.party_code,
        voucher_id=r.voucher_id,
        voucher_item_id=r.voucher_item_id,
        invoice_no=r.invoice_no,
        amount=float(r.amount),
        reconciled_amount=float(r.reconciled_amount),
        remaining_amount=float(r.remaining_amount),
        due_date=r.due_date.isoformat() if r.due_date else None,
        status=r.status,
        notes=r.notes,
        book_id=r.book_id,
        created_by=r.created_by,
        created_at=r.created_at.isoformat() if r.created_at else None,
        updated_at=r.updated_at.isoformat() if r.updated_at else None,
    )


def _update_status(r: Reconciliation):
    """根据核销金额更新状态"""
    if r.remaining_amount == 0:
        r.status = "reconciled"
    elif r.reconciled_amount > 0 and r.reconciled_amount < r.amount:
        r.status = "partial"
    else:
        r.status = "pending"


# ========== API 端点 ==========

@router.get("", response_model=PaginatedResponse, summary="应收应付列表")
async def list_reconciliations(
    reconciliation_type: Optional[str] = Query(None, description="类型: ar/ap"),
    party_type: Optional[str] = Query(None, description="往来方类型: customer/supplier"),
    party_name: Optional[str] = Query(None, description="客户/供应商名称（模糊搜索）"),
    status: Optional[str] = Query(None, description="状态: pending/partial/reconciled"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取应收应付列表，支持筛选和分页"""
    query = select(Reconciliation)
    count_query = select(func.count(Reconciliation.id))

    base_filters = [Reconciliation.book_id == current_book.id]
    if reconciliation_type:
        base_filters.append(Reconciliation.reconciliation_type == reconciliation_type)
    if party_type:
        base_filters.append(Reconciliation.party_type == party_type)
    if party_name:
        base_filters.append(Reconciliation.party_name.ilike(f"%{party_name}%"))
    if status:
        base_filters.append(Reconciliation.status == status)
    if start_date:
        base_filters.append(Reconciliation.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        base_filters.append(Reconciliation.created_at <= datetime.fromisoformat(end_date) + timedelta(days=1))

    if base_filters:
        query = query.where(and_(*base_filters))
        count_query = count_query.where(and_(*base_filters))

    # 总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(Reconciliation.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse(
        items=[_build_response(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ReconciliationResponse, summary="创建核销记录")
async def create_reconciliation(
    data: ReconciliationCreate,
    current_user: User = Depends(require_permission("voucher:create")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """创建新的应收应付核销记录"""
    amount = Decimal(str(data.amount))
    r = Reconciliation(
        reconciliation_type=data.reconciliation_type,
        party_type=data.party_type,
        party_name=data.party_name,
        party_code=data.party_code,
        voucher_id=data.voucher_id,
        voucher_item_id=data.voucher_item_id,
        invoice_no=data.invoice_no,
        amount=amount,
        reconciled_amount=Decimal("0"),
        remaining_amount=amount,
        due_date=date.fromisoformat(data.due_date) if data.due_date else None,
        status="pending",
        notes=data.notes,
        book_id=current_book.id,
        created_by=current_user.id,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    logger.info(f"用户 {current_user.username} 创建了核销记录: {r.party_name} - {r.amount}")
    return _build_response(r)


@router.put("/{record_id}", response_model=ReconciliationResponse, summary="更新核销记录")
async def update_reconciliation(
    record_id: int,
    data: ReconciliationUpdate,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """更新核销记录"""
    result = await db.execute(select(Reconciliation).where(Reconciliation.id == record_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="核销记录不存在")

    if data.reconciliation_type is not None:
        r.reconciliation_type = data.reconciliation_type
    if data.party_type is not None:
        r.party_type = data.party_type
    if data.party_name is not None:
        r.party_name = data.party_name
    if data.party_code is not None:
        r.party_code = data.party_code
    if data.invoice_no is not None:
        r.invoice_no = data.invoice_no
    if data.amount is not None:
        new_amount = Decimal(str(data.amount))
        r.amount = new_amount
        r.remaining_amount = r.amount - r.reconciled_amount
        _update_status(r)
    if data.due_date is not None:
        r.due_date = date.fromisoformat(data.due_date) if data.due_date else None
    if data.notes is not None:
        r.notes = data.notes

    await db.commit()
    await db.refresh(r)
    logger.info(f"用户 {current_user.username} 更新了核销记录: {r.party_name} (ID={r.id})")
    return _build_response(r)


@router.delete("/{record_id}", summary="删除核销记录")
async def delete_reconciliation(
    record_id: int,
    current_user: User = Depends(require_permission("voucher:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除核销记录"""
    result = await db.execute(select(Reconciliation).where(Reconciliation.id == record_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="核销记录不存在")

    await db.delete(r)
    await db.commit()
    logger.info(f"用户 {current_user.username} 删除了核销记录: ID={record_id}")
    return {"message": "核销记录已删除"}


@router.post("/{record_id}/write-off", response_model=ReconciliationResponse, summary="核销操作")
async def write_off_reconciliation(
    record_id: int,
    data: WriteOffRequest,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """对指定核销记录进行核销"""
    result = await db.execute(select(Reconciliation).where(Reconciliation.id == record_id))
    r = result.scalar_one_or_none()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="核销记录不存在")

    if r.status == "reconciled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该记录已核销完毕")

    write_off = Decimal(str(data.write_off_amount))
    if write_off <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="核销金额必须大于0")
    if write_off > r.remaining_amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="核销金额不能超过未核销金额")

    r.reconciled_amount += write_off
    r.remaining_amount = r.amount - r.reconciled_amount
    _update_status(r)

    await db.commit()
    await db.refresh(r)
    logger.info(f"用户 {current_user.username} 核销了记录: {r.party_name}, 金额: {write_off}")
    return _build_response(r)


@router.post("/batch-write-off", summary="批量核销")
async def batch_write_off(
    data: BatchWriteOffRequest,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """批量核销"""
    if not data.ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择核销记录")

    result = await db.execute(
        select(Reconciliation).where(Reconciliation.id.in_(data.ids))
    )
    records = result.scalars().all()

    if len(records) != len(data.ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部分核销记录不存在")

    success_count = 0
    for r in records:
        if r.status == "reconciled":
            continue
        write_off = Decimal(str(data.write_off_amounts.get(str(r.id), float(r.remaining_amount)))) if data.write_off_amounts else r.remaining_amount
        if write_off <= 0 or write_off > r.remaining_amount:
            continue
        r.reconciled_amount += write_off
        r.remaining_amount = r.amount - r.reconciled_amount
        _update_status(r)
        success_count += 1

    await db.commit()
    logger.info(f"用户 {current_user.username} 批量核销了 {success_count} 条记录")
    return {"message": f"批量核销完成，共处理 {success_count} 条记录"}


@router.get("/aging", response_model=AgingResponse, summary="账龄分析")
async def get_aging_analysis(
    reconciliation_type: Optional[str] = Query(None, description="类型: ar/ap"),
    party_type: Optional[str] = Query(None, description="往来方类型: customer/supplier"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取账龄分析数据"""
    filters = [
        Reconciliation.book_id == current_book.id,
        Reconciliation.status.in_(["pending", "partial"]),
    ]
    if reconciliation_type:
        filters.append(Reconciliation.reconciliation_type == reconciliation_type)
    if party_type:
        filters.append(Reconciliation.party_type == party_type)

    result = await db.execute(
        select(Reconciliation).where(and_(*filters)).order_by(Reconciliation.party_name)
    )
    records = result.scalars().all()

    today = date.today()
    aging_buckets = {
        "aging_0_30": 0.0,
        "aging_30_60": 0.0,
        "aging_60_90": 0.0,
        "aging_90_180": 0.0,
        "aging_180_365": 0.0,
        "aging_365_plus": 0.0,
    }

    # 按往来方分组
    party_map = {}
    for r in records:
        key = (r.party_type, r.party_name)
        if key not in party_map:
            party_map[key] = {
                "party_type": r.party_type,
                "party_name": r.party_name,
                "party_code": r.party_code,
                "amount": 0.0,
                "aging_0_30": 0.0,
                "aging_30_60": 0.0,
                "aging_60_90": 0.0,
                "aging_90_180": 0.0,
                "aging_180_365": 0.0,
                "aging_365_plus": 0.0,
            }

        remaining = float(r.remaining_amount)
        bucket = _to_aging_bucket(r.due_date, today) if r.due_date else "aging_365_plus"
        party_map[key]["amount"] += remaining
        party_map[key][bucket] += remaining
        aging_buckets[bucket] += remaining

    items = list(party_map.values())
    items.sort(key=lambda x: x["amount"], reverse=True)

    total_amount = sum(aging_buckets.values())
    aging_labels = [
        ("30天内", "aging_0_30"),
        ("30-60天", "aging_30_60"),
        ("60-90天", "aging_60_90"),
        ("90-180天", "aging_90_180"),
        ("180-365天", "aging_180_365"),
        ("1年以上", "aging_365_plus"),
    ]
    summary = []
    for label, key in aging_labels:
        amt = aging_buckets[key]
        summary.append(AgingSummaryItem(
            label=label,
            amount=round(amt, 2),
            percentage=round(amt / total_amount * 100, 2) if total_amount > 0 else 0,
        ))

    return AgingResponse(
        items=[AgingItem(**it) for it in items],
        summary=summary,
    )


@router.get("/statement/{party_type}/{party_name}", response_model=StatementResponse, summary="客户/供应商对账单")
async def get_party_statement(
    party_type: str,
    party_name: str,
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取客户/供应商对账单"""
    start_dt = datetime.fromisoformat(start_date).replace(hour=0, minute=0, second=0)
    end_dt = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59)

    # 查询期初余额（start_date之前的未核销金额）
    opening_result = await db.execute(
        select(func.coalesce(func.sum(Reconciliation.remaining_amount), 0))
        .where(
            and_(
                Reconciliation.book_id == current_book.id,
                Reconciliation.party_type == party_type,
                Reconciliation.party_name == party_name,
                Reconciliation.status.in_(["pending", "partial"]),
                Reconciliation.created_at < start_dt,
            )
        )
    )
    opening_balance = float(opening_result.scalar() or 0)

    # 查询本期明细
    detail_result = await db.execute(
        select(Reconciliation)
        .where(
            and_(
                Reconciliation.book_id == current_book.id,
                Reconciliation.party_type == party_type,
                Reconciliation.party_name == party_name,
                Reconciliation.created_at >= start_dt,
                Reconciliation.created_at <= end_dt,
            )
        )
        .order_by(Reconciliation.created_at)
    )
    records = detail_result.scalars().all()

    items = []
    running_balance = opening_balance
    total_debit = 0.0
    total_credit = 0.0

    for r in records:
        # 应收(ar)增加记借方，应付(ap)增加记贷方
        if r.reconciliation_type == "ar":
            debit = float(r.amount)
            credit = float(r.reconciled_amount)
        else:
            debit = float(r.reconciled_amount)
            credit = float(r.amount)

        running_balance += debit - credit
        total_debit += debit
        total_credit += credit

        items.append(StatementItem(
            date=r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
            document_type="核销记录",
            document_no=r.invoice_no or "",
            description=f"{'应收' if r.reconciliation_type == 'ar' else '应付'} - {r.notes or ''}",
            debit_amount=round(debit, 2),
            credit_amount=round(credit, 2),
            balance=round(running_balance, 2),
        ))

    closing_balance = running_balance

    return StatementResponse(
        party_type=party_type,
        party_name=party_name,
        party_code=records[0].party_code if records else None,
        start_date=start_date,
        end_date=end_date,
        opening_balance=round(opening_balance, 2),
        items=items,
        total_debit=round(total_debit, 2),
        total_credit=round(total_credit, 2),
        closing_balance=round(closing_balance, 2),
    )


@router.get("/party-names", summary="获取往来方名称列表")
async def get_party_names(
    party_type: Optional[str] = Query(None, description="往来方类型"),
    reconciliation_type: Optional[str] = Query(None, description="类型: ar/ap"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取当前账套下所有往来方名称（用于下拉选择）"""
    filters = [Reconciliation.book_id == current_book.id]
    if party_type:
        filters.append(Reconciliation.party_type == party_type)
    if reconciliation_type:
        filters.append(Reconciliation.reconciliation_type == reconciliation_type)

    result = await db.execute(
        select(
            Reconciliation.party_type,
            Reconciliation.party_name,
            Reconciliation.party_code,
        )
        .where(and_(*filters))
        .distinct()
        .order_by(Reconciliation.party_name)
    )
    rows = result.all()

    return [
        {"party_type": row[0], "party_name": row[1], "party_code": row[2]}
        for row in rows
    ]