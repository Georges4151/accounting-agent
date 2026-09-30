"""
会计期间管理 API
提供结账、反结账、期间状态查询等功能
"""
import logging
from calendar import monthrange
from datetime import datetime, date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from models.user import User
from models.voucher import Voucher
from models.period_close import AccountingPeriod
from auth.middleware import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/period", tags=["会计期间"])


# ========== Pydantic 模型 ==========

class PeriodOut(BaseModel):
    id: int
    book_id: int
    period_year: int
    period_month: int
    status: str
    closed_at: str | None = None
    closed_by: int | None = None
    closed_by_name: str | None = None
    reopened_at: str | None = None
    reopened_by: int | None = None
    reopened_by_name: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


class PeriodCheckResult(BaseModel):
    can_close: bool
    reason: str = ""
    checks: list[dict] = []


class CloseResult(BaseModel):
    success: bool
    message: str
    period: PeriodOut | None = None


# ========== 辅助函数 ==========

async def _get_or_create_periods(db: AsyncSession, book_id: int, year: int) -> list[AccountingPeriod]:
    """获取或创建指定年度所有月份的会计期间记录"""
    result = await db.execute(
        select(AccountingPeriod).where(
            and_(
                AccountingPeriod.book_id == book_id,
                AccountingPeriod.period_year == year,
            )
        ).order_by(AccountingPeriod.period_month)
    )
    periods = list(result.scalars().all())

    existing_months = {p.period_month for p in periods}

    for month in range(1, 13):
        if month not in existing_months:
            period = AccountingPeriod(
                book_id=book_id,
                period_year=year,
                period_month=month,
                status="open",
            )
            db.add(period)
            periods.append(period)

    if len([p for p in periods if p.period_month not in existing_months]) > 0:
        await db.flush()

    periods.sort(key=lambda p: p.period_month)
    return periods


async def _get_user_name(db: AsyncSession, user_id: int | None) -> str | None:
    """获取用户名"""
    if user_id is None:
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return user.real_name if user else None


def _period_to_out(period: AccountingPeriod, closed_by_name: str | None = None,
                   reopened_by_name: str | None = None) -> PeriodOut:
    """将模型转换为输出格式"""
    return PeriodOut(
        id=period.id,
        book_id=period.book_id,
        period_year=period.period_year,
        period_month=period.period_month,
        status=period.status,
        closed_at=period.closed_at.isoformat() if period.closed_at else None,
        closed_by=period.closed_by,
        closed_by_name=closed_by_name,
        reopened_at=period.reopened_at.isoformat() if period.reopened_at else None,
        reopened_by=period.reopened_by,
        reopened_by_name=reopened_by_name,
        created_at=period.created_at.isoformat() if period.created_at else None,
    )


# ========== API 接口 ==========

@router.get("/periods", summary="获取会计期间列表")
async def list_periods(
    book_id: int = Query(..., description="账套ID"),
    year: int | None = Query(None, description="会计年度，默认为当前年份"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定账套的会计期间状态列表"""
    if year is None:
        year = datetime.now().year

    periods = await _get_or_create_periods(db, book_id, year)

    # 收集所有需要查询的用户 ID
    user_ids = set()
    for p in periods:
        if p.closed_by:
            user_ids.add(p.closed_by)
        if p.reopened_by:
            user_ids.add(p.reopened_by)

    # 批量查询用户名
    user_names = {}
    if user_ids:
        result = await db.execute(select(User).where(User.id.in_(user_ids)))
        for u in result.scalars().all():
            user_names[u.id] = u.real_name

    items = [
        _period_to_out(p, user_names.get(p.closed_by), user_names.get(p.reopened_by))
        for p in periods
    ]

    return {"periods": items, "year": year}


@router.get("/periods/{period_year}/{period_month}/check", summary="检查是否可以结账")
async def check_period(
    period_year: int,
    period_month: int,
    book_id: int = Query(..., description="账套ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """检查指定期间是否可以结账"""
    checks = []

    # 1. 检查期间是否存在
    result = await db.execute(
        select(AccountingPeriod).where(
            and_(
                AccountingPeriod.book_id == book_id,
                AccountingPeriod.period_year == period_year,
                AccountingPeriod.period_month == period_month,
            )
        )
    )
    period = result.scalar_one_or_none()
    if period is None:
        return PeriodCheckResult(can_close=False, reason="期间不存在", checks=checks)

    if period.status == "closed":
        return PeriodCheckResult(can_close=False, reason="该期间已结账", checks=checks)

    # 2. 检查前一个期间是否已结账（按顺序结账，1月除外）
    if period_month > 1:
        prev_result = await db.execute(
            select(AccountingPeriod).where(
                and_(
                    AccountingPeriod.book_id == book_id,
                    AccountingPeriod.period_year == period_year,
                    AccountingPeriod.period_month == period_month - 1,
                )
            )
        )
        prev_period = prev_result.scalar_one_or_none()
        if prev_period is None or prev_period.status != "closed":
            checks.append({
                "name": "前一期间已结账",
                "passed": False,
                "detail": f"{period_year}年{period_month - 1}月未结账，请按顺序结账"
            })
        else:
            checks.append({"name": "前一期间已结账", "passed": True, "detail": ""})
    else:
        # 1月需要检查上一年12月
        prev_year_result = await db.execute(
            select(AccountingPeriod).where(
                and_(
                    AccountingPeriod.book_id == book_id,
                    AccountingPeriod.period_year == period_year - 1,
                    AccountingPeriod.period_month == 12,
                )
            )
        )
        prev_year_period = prev_year_result.scalar_one_or_none()
        if prev_year_period is None or prev_year_period.status != "closed":
            checks.append({
                "name": "上一年度12月已结账",
                "passed": False,
                "detail": f"{period_year - 1}年12月未结账，请按顺序结账"
            })
        else:
            checks.append({"name": "上一年度12月已结账", "passed": True, "detail": ""})

    # 3. 检查该期间所有凭证是否已过账
    # 计算该期间的起止日期
    _, last_day = monthrange(period_year, period_month)
    start_date = date(period_year, period_month, 1)
    end_date = date(period_year, period_month, last_day)

    result = await db.execute(
        select(func.count(Voucher.id)).where(
            and_(
                Voucher.book_id == book_id,
                Voucher.voucher_date >= start_date,
                Voucher.voucher_date <= end_date,
                Voucher.status != "posted",
            )
        )
    )
    unposted_count = result.scalar() or 0

    if unposted_count > 0:
        checks.append({
            "name": "所有凭证已过账",
            "passed": False,
            "detail": f"还有 {unposted_count} 张凭证未过账"
        })
    else:
        checks.append({"name": "所有凭证已过账", "passed": True, "detail": ""})

    # 4. 检查试算平衡（该期间所有已过账凭证的借方合计=贷方合计）
    result = await db.execute(
        select(Voucher).where(
            and_(
                Voucher.book_id == book_id,
                Voucher.voucher_date >= start_date,
                Voucher.voucher_date <= end_date,
                Voucher.status == "posted",
            )
        )
    )
    vouchers = result.scalars().all()

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    for v in vouchers:
        for item in v.items:
            total_debit += item.debit_amount
            total_credit += item.credit_amount

    if total_debit != total_credit:
        checks.append({
            "name": "试算平衡",
            "passed": False,
            "detail": f"借方合计 {total_debit} ≠ 贷方合计 {total_credit}，差额 {abs(total_debit - total_credit)}"
        })
    else:
        checks.append({"name": "试算平衡", "passed": True, "detail": f"借方=贷方={total_debit}"})

    # 汇总结果
    all_passed = all(c["passed"] for c in checks)
    reason = "所有检查通过，可以结账" if all_passed else "存在未通过的检查项"

    return PeriodCheckResult(can_close=all_passed, reason=reason, checks=checks)


@router.post("/periods/{period_year}/{period_month}/close", summary="结账")
async def close_period(
    period_year: int,
    period_month: int,
    book_id: int = Query(..., description="账套ID"),
    current_user: User = Depends(require_role("admin", "accountant")),
    db: AsyncSession = Depends(get_db),
):
    """对指定期间执行结账操作"""
    # 先检查是否可以结账
    check_result = await check_period(
        period_year=period_year,
        period_month=period_month,
        book_id=book_id,
        current_user=current_user,
        db=db,
    )

    if not check_result.can_close:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=check_result.reason
        )

    # 获取或创建期间记录
    result = await db.execute(
        select(AccountingPeriod).where(
            and_(
                AccountingPeriod.book_id == book_id,
                AccountingPeriod.period_year == period_year,
                AccountingPeriod.period_month == period_month,
            )
        )
    )
    period = result.scalar_one_or_none()

    if period is None:
        period = AccountingPeriod(
            book_id=book_id,
            period_year=period_year,
            period_month=period_month,
            status="open",
        )
        db.add(period)
        await db.flush()

    period.status = "closed"
    period.closed_at = datetime.now()
    period.closed_by = current_user.id
    period.reopened_at = None
    period.reopened_by = None

    await db.commit()
    await db.refresh(period)

    closed_by_name = await _get_user_name(db, period.closed_by)
    logger.info(f"用户 {current_user.username} 对账套 {book_id} 的 {period_year}年{period_month}月 执行了结账")

    return CloseResult(
        success=True,
        message=f"{period_year}年{period_month}月结账成功",
        period=_period_to_out(period, closed_by_name=closed_by_name),
    )


@router.post("/periods/{period_year}/{period_month}/reopen", summary="反结账")
async def reopen_period(
    period_year: int,
    period_month: int,
    book_id: int = Query(..., description="账套ID"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """对指定期间执行反结账操作（仅管理员）"""
    # 获取期间记录
    result = await db.execute(
        select(AccountingPeriod).where(
            and_(
                AccountingPeriod.book_id == book_id,
                AccountingPeriod.period_year == period_year,
                AccountingPeriod.period_month == period_month,
            )
        )
    )
    period = result.scalar_one_or_none()

    if period is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="期间记录不存在"
        )

    if period.status != "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该期间未结账，无需反结账"
        )

    # 检查后续期间是否已结账（如果后续期间已结账，不允许反结账当前期间）
    next_periods = await db.execute(
        select(AccountingPeriod).where(
            and_(
                AccountingPeriod.book_id == book_id,
                AccountingPeriod.status == "closed",
                AccountingPeriod.period_year >= period_year,
            )
        )
    )
    all_closed = next_periods.scalars().all()

    for np in all_closed:
        if np.period_year > period_year or (np.period_year == period_year and np.period_month > period_month):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"后续期间 {np.period_year}年{np.period_month}月 已结账，请先反结账后续期间"
            )

    period.status = "open"
    period.reopened_at = datetime.now()
    period.reopened_by = current_user.id

    await db.commit()
    await db.refresh(period)

    reopened_by_name = await _get_user_name(db, period.reopened_by)
    logger.info(f"用户 {current_user.username} 对账套 {book_id} 的 {period_year}年{period_month}月 执行了反结账")

    return CloseResult(
        success=True,
        message=f"{period_year}年{period_month}月反结账成功",
        period=_period_to_out(period, reopened_by_name=reopened_by_name),
    )