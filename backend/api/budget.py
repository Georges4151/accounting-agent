"""
预算管理 API 路由
提供预算的 CRUD、执行分析、预警管理等功能
"""
import logging
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_, extract, case
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.budget import Budget, BudgetAlert, BudgetNote
from models.voucher import Voucher, VoucherItem
from auth.middleware import get_current_user, require_permission
from auth.book_context import get_current_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/budgets", tags=["预算管理"])


# ========== 请求/响应模型 ==========

class BudgetCreate(BaseModel):
    """创建预算请求体"""
    name: str = Field(..., description="预算名称")
    year: int = Field(..., ge=2000, le=2099, description="预算年份")
    month: int = Field(default=0, ge=0, le=12, description="预算月份, 0=年度预算")
    account_code: str = Field(..., description="科目编码")
    account_name: str = Field(..., description="科目名称")
    budget_amount: float = Field(..., gt=0, description="预算金额")


class BudgetUpdate(BaseModel):
    """更新预算请求体"""
    name: Optional[str] = Field(None, description="预算名称")
    year: Optional[int] = Field(None, ge=2000, le=2099, description="预算年份")
    month: Optional[int] = Field(None, ge=0, le=12, description="预算月份")
    account_code: Optional[str] = Field(None, description="科目编码")
    account_name: Optional[str] = Field(None, description="科目名称")
    budget_amount: Optional[float] = Field(None, gt=0, description="预算金额")
    status: Optional[str] = Field(None, description="状态: active/closed")


class BudgetAlertCreate(BaseModel):
    """创建预警请求体"""
    alert_type: str = Field(..., description="预警类型: overspend/threshold")
    threshold_percentage: float = Field(..., ge=1, le=200, description="触发阈值百分比")


class BudgetAlertResponse(BaseModel):
    """预警响应体"""
    id: int
    budget_id: int
    budget_name: str = ""
    account_code: str = ""
    account_name: str = ""
    budget_amount: float = 0
    actual_amount: float = 0
    used_percentage: float = 0
    alert_type: str
    threshold_percentage: float
    is_triggered: bool
    triggered_at: Optional[str]
    notified: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class BudgetResponse(BaseModel):
    """预算响应体"""
    id: int
    name: str
    year: int
    month: int
    account_code: str
    account_name: str
    budget_amount: float
    actual_amount: float = 0
    used_percentage: float = 0
    status: str
    created_by: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class BudgetSummaryResponse(BaseModel):
    """预算汇总响应体"""
    total_budget: float = 0
    total_actual: float = 0
    overall_percentage: float = 0
    alert_count: int = 0
    budget_count: int = 0
    categories: list = []


class MonthlyExecution(BaseModel):
    """月度执行数据"""
    month: int
    budget_amount: float = 0
    actual_amount: float = 0
    used_percentage: float = 0


class BudgetExecutionResponse(BaseModel):
    """预算执行详情响应体"""
    budget: BudgetResponse
    monthly_executions: List[MonthlyExecution] = []
    trend: List[dict] = []


class BudgetNoteResponse(BaseModel):
    """预算备注响应体"""
    id: int
    budget_id: int
    note_text: str
    created_by: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ========== 辅助函数 ==========

async def _get_actual_amount(
    db: AsyncSession,
    account_code: str,
    year: int,
    month: int = 0,
) -> Decimal:
    """
    计算指定科目在指定年月的实际发生额
    从已审核/已过账的凭证中汇总借方金额
    """
    conditions = [
        Voucher.status.in_(["reviewed", "posted"]),
        VoucherItem.account_code == account_code,
        extract("year", Voucher.voucher_date) == year,
    ]

    if month > 0:
        conditions.append(extract("month", Voucher.voucher_date) == month)

    query = (
        select(func.coalesce(func.sum(VoucherItem.debit_amount), 0))
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(and_(*conditions))
    )

    result = await db.execute(query)
    total = result.scalar() or Decimal("0")
    return total


async def _get_monthly_actuals(
    db: AsyncSession,
    account_code: str,
    year: int,
) -> dict:
    """
    获取指定科目在指定年份每个月的实际发生额
    返回 {month: amount} 字典
    """
    query = (
        select(
            extract("month", Voucher.voucher_date).label("month"),
            func.coalesce(func.sum(VoucherItem.debit_amount), 0).label("amount"),
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            and_(
                Voucher.status.in_(["reviewed", "posted"]),
                VoucherItem.account_code == account_code,
                extract("year", Voucher.voucher_date) == year,
            )
        )
        .group_by(extract("month", Voucher.voucher_date))
        .order_by(extract("month", Voucher.voucher_date))
    )

    result = await db.execute(query)
    rows = result.all()
    return {int(row.month): float(row.amount) for row in rows}


async def _check_and_trigger_alert(
    db: AsyncSession,
    budget: Budget,
    actual_amount: Decimal,
):
    """检查预算是否需要触发预警"""
    if actual_amount <= 0 or budget.budget_amount <= 0:
        return

    used_pct = float(actual_amount) / float(budget.budget_amount) * 100

    # 查询所有未触发的预警
    stmt = (
        select(BudgetAlert)
        .where(
            and_(
                BudgetAlert.budget_id == budget.id,
                BudgetAlert.is_triggered == False,
            )
        )
    )
    result = await db.execute(stmt)
    alerts = result.scalars().all()

    for alert in alerts:
        threshold = float(alert.threshold_percentage)
        if used_pct >= threshold:
            alert.is_triggered = True
            alert.triggered_at = datetime.now()
            logger.info(
                f"预算预警触发: budget={budget.name}, "
                f"account={budget.account_code}, "
                f"used={used_pct:.1f}%, threshold={threshold}%"
            )


# ========== API 端点 ==========

@router.get("", response_model=List[BudgetResponse], summary="预算列表")
async def list_budgets(
    year: Optional[int] = Query(None, description="预算年份"),
    month: Optional[int] = Query(None, description="预算月份"),
    status: Optional[str] = Query(None, description="状态: active/closed"),
    account_code: Optional[str] = Query(None, description="科目编码"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取预算列表，含实际金额和使用百分比"""
    query = select(Budget)

    filters = [Budget.book_id == current_book.id]
    if year is not None:
        filters.append(Budget.year == year)
    if month is not None:
        filters.append(Budget.month == month)
    if status is not None:
        filters.append(Budget.status == status)
    if account_code is not None:
        filters.append(Budget.account_code.ilike(f"%{account_code}%"))

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(Budget.account_code, Budget.year.desc(), Budget.month)
    result = await db.execute(query)
    budgets = result.scalars().all()

    items = []
    for b in budgets:
        actual = await _get_actual_amount(db, b.account_code, b.year, b.month)
        actual_float = float(actual)
        budget_float = float(b.budget_amount)
        used_pct = round(actual_float / budget_float * 100, 2) if budget_float > 0 else 0

        # 检查预警
        await _check_and_trigger_alert(db, b, actual)

        items.append(BudgetResponse(
            id=b.id,
            name=b.name,
            year=b.year,
            month=b.month,
            account_code=b.account_code,
            account_name=b.account_name,
            budget_amount=budget_float,
            actual_amount=actual_float,
            used_percentage=used_pct,
            status=b.status,
            created_by=b.created_by,
            created_at=b.created_at.isoformat() if b.created_at else None,
            updated_at=b.updated_at.isoformat() if b.updated_at else None,
        ))

    await db.commit()
    return items


@router.post("", response_model=BudgetResponse, summary="创建预算")
async def create_budget(
    budget_data: BudgetCreate,
    current_user: User = Depends(require_permission("voucher:create")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """创建新的预算项"""
    # 检查是否已存在相同科目+年月的预算
    stmt = select(Budget).where(
        and_(
            Budget.account_code == budget_data.account_code,
            Budget.year == budget_data.year,
            Budget.month == budget_data.month,
            Budget.book_id == current_book.id,
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"该科目在 {budget_data.year}年{'年度' if budget_data.month == 0 else str(budget_data.month) + '月'} 已存在预算",
        )

    budget = Budget(
        name=budget_data.name,
        year=budget_data.year,
        month=budget_data.month,
        account_code=budget_data.account_code,
        account_name=budget_data.account_name,
        budget_amount=Decimal(str(budget_data.budget_amount)),
        status="active",
        created_by=current_user.id,
        book_id=current_book.id,
    )
    db.add(budget)
    await db.commit()
    await db.refresh(budget)
    logger.info(f"用户 {current_user.username} 创建了预算: {budget.name} - {budget.account_code}")

    return BudgetResponse(
        id=budget.id,
        name=budget.name,
        year=budget.year,
        month=budget.month,
        account_code=budget.account_code,
        account_name=budget.account_name,
        budget_amount=float(budget.budget_amount),
        actual_amount=0,
        used_percentage=0,
        status=budget.status,
        created_by=budget.created_by,
        created_at=budget.created_at.isoformat() if budget.created_at else None,
        updated_at=budget.updated_at.isoformat() if budget.updated_at else None,
    )


@router.put("/{budget_id}", response_model=BudgetResponse, summary="更新预算")
async def update_budget(
    budget_id: int,
    budget_data: BudgetUpdate,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """更新预算信息"""
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预算不存在")

    if budget_data.name is not None:
        budget.name = budget_data.name
    if budget_data.year is not None:
        budget.year = budget_data.year
    if budget_data.month is not None:
        budget.month = budget_data.month
    if budget_data.account_code is not None:
        budget.account_code = budget_data.account_code
    if budget_data.account_name is not None:
        budget.account_name = budget_data.account_name
    if budget_data.budget_amount is not None:
        budget.budget_amount = Decimal(str(budget_data.budget_amount))
    if budget_data.status is not None:
        budget.status = budget_data.status

    await db.commit()
    await db.refresh(budget)
    logger.info(f"用户 {current_user.username} 更新了预算: {budget.name}")

    actual = await _get_actual_amount(db, budget.account_code, budget.year, budget.month)
    actual_float = float(actual)
    budget_float = float(budget.budget_amount)
    used_pct = round(actual_float / budget_float * 100, 2) if budget_float > 0 else 0

    return BudgetResponse(
        id=budget.id,
        name=budget.name,
        year=budget.year,
        month=budget.month,
        account_code=budget.account_code,
        account_name=budget.account_name,
        budget_amount=budget_float,
        actual_amount=actual_float,
        used_percentage=used_pct,
        status=budget.status,
        created_by=budget.created_by,
        created_at=budget.created_at.isoformat() if budget.created_at else None,
        updated_at=budget.updated_at.isoformat() if budget.updated_at else None,
    )


@router.delete("/{budget_id}", summary="删除预算")
async def delete_budget(
    budget_id: int,
    current_user: User = Depends(require_permission("voucher:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除预算"""
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预算不存在")

    await db.delete(budget)
    await db.commit()
    logger.info(f"用户 {current_user.username} 删除了预算: {budget.name}")
    return {"message": "预算已删除"}


@router.get("/{budget_id}/execution", response_model=BudgetExecutionResponse, summary="预算执行详情")
async def get_budget_execution(
    budget_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取预算执行详情，包含月度数据和趋势"""
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预算不存在")

    actual = await _get_actual_amount(db, budget.account_code, budget.year, budget.month)
    actual_float = float(actual)
    budget_float = float(budget.budget_amount)
    used_pct = round(actual_float / budget_float * 100, 2) if budget_float > 0 else 0

    budget_resp = BudgetResponse(
        id=budget.id,
        name=budget.name,
        year=budget.year,
        month=budget.month,
        account_code=budget.account_code,
        account_name=budget.account_name,
        budget_amount=budget_float,
        actual_amount=actual_float,
        used_percentage=used_pct,
        status=budget.status,
        created_by=budget.created_by,
        created_at=budget.created_at.isoformat() if budget.created_at else None,
        updated_at=budget.updated_at.isoformat() if budget.updated_at else None,
    )

    monthly_actuals = await _get_monthly_actuals(db, budget.account_code, budget.year)

    monthly_executions = []
    trend = []
    cumulative_actual = 0.0

    # 年度预算：显示12个月
    # 月度预算：显示当月
    months_to_show = range(1, 13) if budget.month == 0 else [budget.month]

    for m in months_to_show:
        month_actual = monthly_actuals.get(m, 0)
        cumulative_actual += month_actual

        # 月度预算均摊或当月预算
        if budget.month == 0:
            month_budget = budget_float / 12
        else:
            month_budget = budget_float if m == budget.month else 0

        month_pct = round(month_actual / month_budget * 100, 2) if month_budget > 0 else 0

        monthly_executions.append(MonthlyExecution(
            month=m,
            budget_amount=round(month_budget, 2),
            actual_amount=round(month_actual, 2),
            used_percentage=month_pct,
        ))

        trend.append({
            "month": m,
            "budget": round(month_budget, 2),
            "actual": round(month_actual, 2),
            "cumulative": round(cumulative_actual, 2),
        })

    return BudgetExecutionResponse(
        budget=budget_resp,
        monthly_executions=monthly_executions,
        trend=trend,
    )


@router.get("/alerts", response_model=List[BudgetAlertResponse], summary="获取预算预警")
async def get_budget_alerts(
    triggered_only: bool = Query(False, description="仅显示已触发的预警"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取预算预警列表"""
    query = select(BudgetAlert)
    if triggered_only:
        query = query.where(BudgetAlert.is_triggered == True)

    query = query.order_by(BudgetAlert.is_triggered.desc(), BudgetAlert.triggered_at.desc())
    result = await db.execute(query)
    alerts = result.scalars().all()

    items = []
    for alert in alerts:
        # 获取关联的预算信息
        budget_result = await db.execute(select(Budget).where(Budget.id == alert.budget_id))
        budget = budget_result.scalar_one_or_none()

        if budget:
            actual = await _get_actual_amount(db, budget.account_code, budget.year, budget.month)
            actual_float = float(actual)
            budget_float = float(budget.budget_amount)
            used_pct = round(actual_float / budget_float * 100, 2) if budget_float > 0 else 0

            items.append(BudgetAlertResponse(
                id=alert.id,
                budget_id=alert.budget_id,
                budget_name=budget.name,
                account_code=budget.account_code,
                account_name=budget.account_name,
                budget_amount=budget_float,
                actual_amount=actual_float,
                used_percentage=used_pct,
                alert_type=alert.alert_type,
                threshold_percentage=float(alert.threshold_percentage),
                is_triggered=alert.is_triggered,
                triggered_at=alert.triggered_at.isoformat() if alert.triggered_at else None,
                notified=alert.notified,
                created_at=alert.created_at.isoformat() if alert.created_at else None,
            ))
        else:
            items.append(BudgetAlertResponse(
                id=alert.id,
                budget_id=alert.budget_id,
                alert_type=alert.alert_type,
                threshold_percentage=float(alert.threshold_percentage),
                is_triggered=alert.is_triggered,
                triggered_at=alert.triggered_at.isoformat() if alert.triggered_at else None,
                notified=alert.notified,
                created_at=alert.created_at.isoformat() if alert.created_at else None,
            ))

    return items


@router.post("/{budget_id}/alerts", response_model=BudgetAlertResponse, summary="创建预警阈值")
async def create_budget_alert(
    budget_id: int,
    alert_data: BudgetAlertCreate,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """为预算创建预警阈值"""
    # 检查预算是否存在
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预算不存在")

    alert = BudgetAlert(
        budget_id=budget_id,
        alert_type=alert_data.alert_type,
        threshold_percentage=Decimal(str(alert_data.threshold_percentage)),
        is_triggered=False,
        notified=False,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    actual = await _get_actual_amount(db, budget.account_code, budget.year, budget.month)
    actual_float = float(actual)
    budget_float = float(budget.budget_amount)
    used_pct = round(actual_float / budget_float * 100, 2) if budget_float > 0 else 0

    # 检查是否应该立即触发
    await _check_and_trigger_alert(db, budget, actual)
    await db.commit()
    await db.refresh(alert)

    logger.info(f"用户 {current_user.username} 为预算 {budget.name} 创建了预警: {alert_data.alert_type} @ {alert_data.threshold_percentage}%")

    return BudgetAlertResponse(
        id=alert.id,
        budget_id=alert.budget_id,
        budget_name=budget.name,
        account_code=budget.account_code,
        account_name=budget.account_name,
        budget_amount=budget_float,
        actual_amount=actual_float,
        used_percentage=used_pct,
        alert_type=alert.alert_type,
        threshold_percentage=float(alert.threshold_percentage),
        is_triggered=alert.is_triggered,
        triggered_at=alert.triggered_at.isoformat() if alert.triggered_at else None,
        notified=alert.notified,
        created_at=alert.created_at.isoformat() if alert.created_at else None,
    )


@router.delete("/alerts/{alert_id}", summary="删除预警")
async def delete_budget_alert(
    alert_id: int,
    current_user: User = Depends(require_permission("voucher:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除预算预警"""
    result = await db.execute(select(BudgetAlert).where(BudgetAlert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预警不存在")

    await db.delete(alert)
    await db.commit()
    logger.info(f"用户 {current_user.username} 删除了预警 ID={alert_id}")
    return {"message": "预警已删除"}


@router.get("/summary", response_model=BudgetSummaryResponse, summary="预算汇总")
async def get_budget_summary(
    year: int = Query(..., description="汇总年份"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取预算汇总信息"""
    # 获取所有活跃预算
    result = await db.execute(
        select(Budget).where(
            and_(
                Budget.year == year,
                Budget.status == "active",
                Budget.book_id == current_book.id,
            )
        )
    )
    budgets = result.scalars().all()

    total_budget = 0.0
    total_actual = 0.0
    alert_count = 0

    # 按科目类别分组（取科目编码前4位作为类别）
    category_map = {}

    for b in budgets:
        actual = await _get_actual_amount(db, b.account_code, b.year, b.month)
        actual_float = float(actual)
        budget_float = float(b.budget_amount)

        total_budget += budget_float
        total_actual += actual_float

        category_key = b.account_code[:4] if len(b.account_code) >= 4 else b.account_code
        if category_key not in category_map:
            category_map[category_key] = {
                "category": category_key,
                "total_budget": 0.0,
                "total_actual": 0.0,
                "count": 0,
            }
        category_map[category_key]["total_budget"] += budget_float
        category_map[category_key]["total_actual"] += actual_float
        category_map[category_key]["count"] += 1

    # 统计预警数量
    alert_result = await db.execute(
        select(func.count(BudgetAlert.id)).where(
            and_(
                BudgetAlert.is_triggered == True,
                BudgetAlert.notified == False,
            )
        )
    )
    alert_count = alert_result.scalar() or 0

    overall_pct = round(total_actual / total_budget * 100, 2) if total_budget > 0 else 0

    categories = []
    for cat in category_map.values():
        cat["used_percentage"] = round(
            cat["total_actual"] / cat["total_budget"] * 100, 2
        ) if cat["total_budget"] > 0 else 0
        categories.append(cat)

    categories.sort(key=lambda x: x["used_percentage"], reverse=True)

    return BudgetSummaryResponse(
        total_budget=round(total_budget, 2),
        total_actual=round(total_actual, 2),
        overall_percentage=overall_pct,
        alert_count=alert_count,
        budget_count=len(budgets),
        categories=categories,
    )


# ========== 预算备注 ==========

class BudgetNoteCreate(BaseModel):
    """创建备注请求体"""
    note_text: str = Field(..., min_length=1, description="备注内容")


@router.post("/{budget_id}/notes", response_model=BudgetNoteResponse, summary="添加预算备注")
async def add_budget_note(
    budget_id: int,
    note_data: BudgetNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为预算添加备注"""
    result = await db.execute(select(Budget).where(Budget.id == budget_id))
    budget = result.scalar_one_or_none()
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="预算不存在")

    note = BudgetNote(
        budget_id=budget_id,
        note_text=note_data.note_text,
        created_by=current_user.id,
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    return BudgetNoteResponse(
        id=note.id,
        budget_id=note.budget_id,
        note_text=note.note_text,
        created_by=note.created_by,
        created_at=note.created_at.isoformat() if note.created_at else None,
    )


@router.get("/{budget_id}/notes", response_model=List[BudgetNoteResponse], summary="获取预算备注")
async def get_budget_notes(
    budget_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取预算的备注列表"""
    result = await db.execute(
        select(BudgetNote)
        .where(BudgetNote.budget_id == budget_id)
        .order_by(BudgetNote.created_at.desc())
    )
    notes = result.scalars().all()

    return [
        BudgetNoteResponse(
            id=n.id,
            budget_id=n.budget_id,
            note_text=n.note_text,
            created_by=n.created_by,
            created_at=n.created_at.isoformat() if n.created_at else None,
        )
        for n in notes
    ]