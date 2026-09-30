"""
税务管理 API 路由
提供税务计算、记录管理、分析汇总和截止提醒功能
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.tax import TaxRecord, TaxDeadline, TaxSummary
from auth.middleware import get_current_user
from auth.book_context import get_current_book
from services.tax_service import (
    TAX_CALCULATORS,
    DEFAULT_RATES,
    get_tax_summary,
    get_tax_analysis,
    calculate_vat,
    calculate_income_tax,
    calculate_surtax,
    calculate_stamp_tax,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tax", tags=["税务管理"])


# ========== 请求/响应模型 ==========

class TaxCalculateRequest(BaseModel):
    """税务计算请求体"""
    tax_type: str = Field(..., description="税种: 增值税/企业所得税/附加税/印花税/其他")
    period: str = Field(..., description="税务期间 YYYY-MM")
    tax_rate: Optional[float] = Field(None, description="自定义税率（可选）")


class TaxRecordUpdate(BaseModel):
    """更新税务记录请求体"""
    tax_amount: Optional[float] = Field(None, description="应纳税额")
    taxable_amount: Optional[float] = Field(None, description="应纳税额基数")
    tax_rate: Optional[float] = Field(None, description="税率")
    notes: Optional[str] = Field(None, description="备注")


class TaxPayRequest(BaseModel):
    """标记已缴请求体"""
    paid_amount: float = Field(..., description="实缴金额")
    paid_date: Optional[str] = Field(None, description="缴纳日期 YYYY-MM-DD")


class TaxDeadlineCreate(BaseModel):
    """添加截止提醒请求体"""
    tax_type: str = Field(..., description="税种")
    deadline_date: str = Field(..., description="截止日期 YYYY-MM-DD")
    period: str = Field(..., description="所属期间 YYYY-MM")
    reminder_days: int = Field(default=7, description="提前提醒天数")


class PaginatedResponse(BaseModel):
    """分页响应"""
    total: int
    page: int
    page_size: int
    items: List[dict]


# ========== 辅助函数 ==========

TAX_TYPE_LABELS = {
    "增值税": "增值税",
    "企业所得税": "企业所得税",
    "附加税": "附加税",
    "印花税": "印花税",
    "其他": "其他",
}

STATUS_LABELS = {
    "pending": "待计算",
    "calculated": "已计算",
    "paid": "已缴纳",
    "overdue": "逾期",
}


def _get_default_due_date(period: str, tax_type: str) -> date:
    """获取默认申报截止日期（次月15日）"""
    try:
        year, month = period.split("-")
        year_int = int(year)
        month_int = int(month)
        # 次月15日
        if month_int == 12:
            return date(year_int + 1, 1, 15)
        return date(year_int, month_int + 1, 15)
    except (ValueError, IndexError):
        return date.today() + timedelta(days=15)


async def _check_overdue_records(db: AsyncSession) -> None:
    """检查并更新逾期记录"""
    today = date.today()
    result = await db.execute(
        select(TaxRecord).where(
            TaxRecord.status == "calculated",
            TaxRecord.due_date < today,
        )
    )
    overdue = result.scalars().all()
    for r in overdue:
        r.status = "overdue"
    if overdue:
        await db.flush()


# ========== API 端点 ==========

@router.get("/records", summary="获取税务记录列表")
async def list_tax_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    tax_type: Optional[str] = Query(None, description="按税种筛选"),
    period: Optional[str] = Query(None, description="按期间筛选"),
    status: Optional[str] = Query(None, description="按状态筛选: pending/calculated/paid/overdue"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取税务记录列表，支持分页和筛选"""
    await _check_overdue_records(db)

    query = select(TaxRecord)
    count_query = select(func.count(TaxRecord.id))

    filters = [TaxRecord.book_id == current_book.id]
    if tax_type:
        filters.append(TaxRecord.tax_type == tax_type)
    if period:
        filters.append(TaxRecord.tax_period == period)
    if status:
        filters.append(TaxRecord.status == status)
    if start_date:
        filters.append(TaxRecord.due_date >= date.fromisoformat(start_date))
    if end_date:
        filters.append(TaxRecord.due_date <= date.fromisoformat(end_date))

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(TaxRecord.tax_period.desc(), TaxRecord.created_at.desc())
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    records = result.scalars().all()

    items = [
        {
            "id": r.id,
            "tax_type": r.tax_type,
            "tax_period": r.tax_period,
            "tax_period_type": r.tax_period_type,
            "taxable_amount": float(r.taxable_amount),
            "tax_rate": float(r.tax_rate),
            "tax_amount": float(r.tax_amount),
            "paid_amount": float(r.paid_amount),
            "remaining_amount": float(r.remaining_amount),
            "status": r.status,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "paid_date": r.paid_date.isoformat() if r.paid_date else None,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]

    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.post("/calculate", summary="计算税费")
async def calculate_tax(
    request: TaxCalculateRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """根据凭证数据自动计算指定期间的税费"""
    tax_type = request.tax_type
    period = request.period
    rate = Decimal(str(request.tax_rate)) if request.tax_rate else None

    calculator = TAX_CALCULATORS.get(tax_type)
    if calculator is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的税种: {tax_type}，支持: {list(TAX_CALCULATORS.keys())}",
        )

    # 执行计算
    result = await calculator(db, period, rate)

    if not result.get("has_data"):
        return {
            "message": f"该期间没有找到{tax_type}相关的凭证数据",
            "tax_type": tax_type,
            "period": period,
            "data": result,
        }

    # 检查是否已存在记录
    existing = await db.execute(
        select(TaxRecord).where(
            TaxRecord.tax_type == tax_type,
            TaxRecord.tax_period == period,
            TaxRecord.book_id == current_book.id,
        )
    )
    existing_record = existing.scalar_one_or_none()

    due_date = _get_default_due_date(period, tax_type)
    tax_amount = Decimal(str(result["tax_amount"]))
    taxable_amount = Decimal(str(result.get("taxable_amount", result.get("revenue", 0))))
    used_rate = rate or DEFAULT_RATES.get(tax_type, Decimal("0"))

    if existing_record:
        # 更新已有记录
        existing_record.taxable_amount = taxable_amount
        existing_record.tax_rate = used_rate
        existing_record.tax_amount = tax_amount
        existing_record.remaining_amount = tax_amount - existing_record.paid_amount
        existing_record.status = "calculated"
        existing_record.due_date = due_date
        existing_record.notes = f"重新计算于 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        record = existing_record
    else:
        # 创建新记录
        record = TaxRecord(
            tax_type=tax_type,
            tax_period=period,
            tax_period_type="monthly",
            taxable_amount=taxable_amount,
            tax_rate=used_rate,
            tax_amount=tax_amount,
            paid_amount=Decimal("0"),
            remaining_amount=tax_amount,
            status="calculated",
            due_date=due_date,
            created_by=current_user.id,
            book_id=current_book.id,
            notes=f"系统自动计算于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            calculation_detail=result,
        )
        db.add(record)

    await db.commit()
    await db.refresh(record)
    logger.info(f"用户 {current_user.username} 计算了 {period} 的{tax_type}")

    return {
        "message": f"{tax_type}计算完成",
        "record": {
            "id": record.id,
            "tax_type": record.tax_type,
            "tax_period": record.tax_period,
            "taxable_amount": float(record.taxable_amount),
            "tax_rate": float(record.tax_rate),
            "tax_amount": float(record.tax_amount),
            "paid_amount": float(record.paid_amount),
            "remaining_amount": float(record.remaining_amount),
            "status": record.status,
            "due_date": record.due_date.isoformat() if record.due_date else None,
            "notes": record.notes,
        },
        "calculation_detail": result,
    }


@router.put("/records/{record_id}", summary="更新税务记录")
async def update_tax_record(
    record_id: int,
    data: TaxRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动调整税务记录"""
    result = await db.execute(
        select(TaxRecord).where(TaxRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="税务记录不存在")

    if data.tax_amount is not None:
        record.tax_amount = Decimal(str(data.tax_amount))
        record.remaining_amount = record.tax_amount - record.paid_amount
    if data.taxable_amount is not None:
        record.taxable_amount = Decimal(str(data.taxable_amount))
    if data.tax_rate is not None:
        record.tax_rate = Decimal(str(data.tax_rate))
    if data.notes is not None:
        record.notes = data.notes

    await db.commit()
    await db.refresh(record)
    logger.info(f"用户 {current_user.username} 更新了税务记录 {record_id}")

    return {
        "message": "更新成功",
        "record": {
            "id": record.id,
            "tax_type": record.tax_type,
            "tax_period": record.tax_period,
            "taxable_amount": float(record.taxable_amount),
            "tax_rate": float(record.tax_rate),
            "tax_amount": float(record.tax_amount),
            "paid_amount": float(record.paid_amount),
            "remaining_amount": float(record.remaining_amount),
            "status": record.status,
            "due_date": record.due_date.isoformat() if record.due_date else None,
            "paid_date": record.paid_date.isoformat() if record.paid_date else None,
            "notes": record.notes,
        },
    }


@router.post("/records/{record_id}/pay", summary="标记已缴")
async def pay_tax(
    record_id: int,
    data: TaxPayRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记税务记录为已缴纳"""
    result = await db.execute(
        select(TaxRecord).where(TaxRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="税务记录不存在")

    paid_amount = Decimal(str(data.paid_amount))
    record.paid_amount = record.paid_amount + paid_amount
    record.remaining_amount = record.tax_amount - record.paid_amount

    if data.paid_date:
        record.paid_date = date.fromisoformat(data.paid_date)
    else:
        record.paid_date = date.today()

    if record.remaining_amount <= 0:
        record.status = "paid"
        record.remaining_amount = Decimal("0")

    record.notes = (record.notes or "") + f"\n{datetime.now().strftime('%Y-%m-%d')} 缴纳 {float(paid_amount):.2f}"

    await db.commit()
    await db.refresh(record)
    logger.info(f"用户 {current_user.username} 标记税务记录 {record_id} 已缴纳 {paid_amount}")

    return {
        "message": "标记已缴成功",
        "record": {
            "id": record.id,
            "tax_type": record.tax_type,
            "tax_period": record.tax_period,
            "tax_amount": float(record.tax_amount),
            "paid_amount": float(record.paid_amount),
            "remaining_amount": float(record.remaining_amount),
            "status": record.status,
            "paid_date": record.paid_date.isoformat() if record.paid_date else None,
        },
    }


@router.get("/summary", summary="税务汇总")
async def tax_summary(
    period: str = Query(..., description="期间 YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定期间的税务汇总"""
    summary = await get_tax_summary(db, period)
    return summary


@router.get("/analysis", summary="税负分析")
async def tax_analysis(
    year: int = Query(..., description="年份"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取年度税负分析"""
    analysis = await get_tax_analysis(db, year)
    return analysis


@router.get("/deadlines", summary="获取截止提醒")
async def get_tax_deadlines(
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取未来30天内的税务申报截止日期"""
    await _check_overdue_records(db)

    today = date.today()
    future_date = today + timedelta(days=30)

    result = await db.execute(
        select(TaxDeadline)
        .where(
            TaxDeadline.deadline_date >= today,
            TaxDeadline.deadline_date <= future_date,
            TaxDeadline.book_id == current_book.id,
        )
        .order_by(TaxDeadline.deadline_date.asc())
    )
    deadlines = list(result.scalars().all())

    # 同时检查 TaxRecord 中即将到期的记录
    record_result = await db.execute(
        select(TaxRecord)
        .where(
            TaxRecord.status.in_(["pending", "calculated"]),
            TaxRecord.due_date >= today,
            TaxRecord.due_date <= future_date,
            TaxRecord.book_id == current_book.id,
        )
        .order_by(TaxRecord.due_date.asc())
    )
    due_records = record_result.scalars().all()

    items = []
    for d in deadlines:
        days_left = (d.deadline_date - today).days
        items.append({
            "id": d.id,
            "source": "deadline",
            "tax_type": d.tax_type,
            "period": d.period,
            "deadline_date": d.deadline_date.isoformat(),
            "days_left": days_left,
            "is_reminded": d.is_reminded,
            "is_overdue": False,
        })

    for r in due_records:
        days_left = (r.due_date - today).days if r.due_date else 0
        items.append({
            "id": r.id,
            "source": "record",
            "tax_type": r.tax_type,
            "period": r.tax_period,
            "deadline_date": r.due_date.isoformat() if r.due_date else "",
            "days_left": days_left,
            "tax_amount": float(r.tax_amount),
            "remaining_amount": float(r.remaining_amount),
            "is_reminded": False,
            "is_overdue": False,
        })

    items.sort(key=lambda x: x["days_left"])

    return {"items": items, "total": len(items)}


@router.post("/deadlines", summary="添加截止提醒")
async def add_tax_deadline(
    data: TaxDeadlineCreate,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """添加税务申报截止日期提醒"""
    deadline = TaxDeadline(
        tax_type=data.tax_type,
        deadline_date=date.fromisoformat(data.deadline_date),
        period=data.period,
        reminder_days=data.reminder_days,
        is_reminded=False,
        book_id=current_book.id,
    )
    db.add(deadline)
    await db.commit()
    await db.refresh(deadline)

    logger.info(f"用户 {current_user.username} 添加了 {data.tax_type} 截止提醒")

    return {
        "message": "添加成功",
        "deadline": {
            "id": deadline.id,
            "tax_type": deadline.tax_type,
            "deadline_date": deadline.deadline_date.isoformat(),
            "period": deadline.period,
            "reminder_days": deadline.reminder_days,
        },
    }