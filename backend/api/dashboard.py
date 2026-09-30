"""
数据看板 API 路由
提供关键财务指标、趋势分析、科目占比、月度对比、健康评分
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_, Integer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.voucher import Voucher, VoucherItem, Account
from models.invoice import Invoice
from models.fixed_asset import FixedAsset
from auth.middleware import get_current_user
from auth.book_context import get_current_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["数据看板"])


# ========== 辅助函数 ==========

def _month_range(period: str) -> tuple:
    """根据月份字符串计算起止日期，如 '2026-08' -> ('2026-08-01', '2026-08-31')"""
    if not period or len(period) != 7:
        now = date.today()
        start = now.replace(day=1)
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = now.replace(month=now.month + 1, day=1) - timedelta(days=1)
        return start.isoformat(), end.isoformat()
    year, month = int(period[:4]), int(period[5:7])
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _prev_month(period: str) -> str:
    """获取上一个月的月份字符串"""
    if not period or len(period) != 7:
        now = date.today()
        first = now.replace(day=1)
        prev = first - timedelta(days=1)
        return prev.strftime("%Y-%m")
    year, month = int(period[:4]), int(period[5:7])
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def _prev_year_month(period: str) -> str:
    """获取去年同月的月份字符串，如 '2026-08' -> '2025-08'"""
    if not period or len(period) != 7:
        now = date.today()
        return f"{now.year - 1}-{now.month:02d}"
    year, month = int(period[:4]), int(period[5:7])
    return f"{year - 1}-{month:02d}"


async def _get_account_balances(
    db: AsyncSession,
    end_date: str,
    start_date: Optional[str] = None,
    book_id: Optional[int] = None,
) -> dict:
    """获取各科目的余额汇总"""
    query = (
        select(
            VoucherItem.account_code,
            VoucherItem.account_name,
            func.sum(VoucherItem.debit_amount).label("total_debit"),
            func.sum(VoucherItem.credit_amount).label("total_credit"),
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            Voucher.status.in_(["reviewed", "posted"]),
            Voucher.voucher_date <= end_date,
        )
        .group_by(VoucherItem.account_code, VoucherItem.account_name)
    )

    if book_id:
        query = query.where(Voucher.book_id == book_id)

    if start_date:
        query = query.where(Voucher.voucher_date >= start_date)

    result = await db.execute(query)
    rows = result.all()

    balances = {}
    for row in rows:
        code = row.account_code
        debit = float(row.total_debit or 0)
        credit = float(row.total_credit or 0)
        balances[code] = {
            "account_name": row.account_name,
            "total_debit": debit,
            "total_credit": credit,
        }
    return balances


async def _get_all_accounts(db: AsyncSession, book_id: Optional[int] = None) -> list:
    """获取所有科目及其类型"""
    query = select(Account).where(Account.is_active == True)
    if book_id:
        query = query.where(Account.book_id == book_id)
    query = query.order_by(Account.account_code)
    result = await db.execute(query)
    return result.scalars().all()


async def _compute_revenue_expense(
    db: AsyncSession, start_date: str, end_date: str, book_id: Optional[int] = None
) -> tuple:
    """计算指定期间的收入和支出总额"""
    balances = await _get_account_balances(db, end_date, start_date, book_id=book_id)
    accounts = await _get_all_accounts(db, book_id=book_id)

    total_revenue = 0.0
    total_expenses = 0.0

    for acc in accounts:
        if acc.account_type not in ("revenue", "expense"):
            continue
        bal = balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        if acc.balance_direction == "credit":
            amount = bal["total_credit"] - bal["total_debit"]
        else:
            amount = bal["total_debit"] - bal["total_credit"]

        if acc.account_type == "revenue":
            total_revenue += amount
        else:
            total_expenses += amount

    return total_revenue, total_expenses


async def _compute_balance_sheet_totals(
    db: AsyncSession, end_date: str, book_id: Optional[int] = None
) -> dict:
    """计算资产负债表各项目总计"""
    balances = await _get_account_balances(db, end_date, book_id=book_id)
    accounts = await _get_all_accounts(db, book_id=book_id)

    total_assets = 0.0
    total_liabilities = 0.0
    total_equity = 0.0
    current_assets = 0.0
    current_liabilities = 0.0

    for acc in accounts:
        bal = balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        if acc.balance_direction == "debit":
            ending = bal["total_debit"] - bal["total_credit"]
        else:
            ending = bal["total_credit"] - bal["total_debit"]

        if acc.account_type == "asset":
            total_assets += ending
            if acc.account_code.startswith("1"):
                current_assets += ending
        elif acc.account_type == "liability":
            total_liabilities += ending
            if acc.account_code.startswith("2"):
                current_liabilities += ending
        elif acc.account_type == "equity":
            total_equity += ending

    return {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
    }


# ========== API 端点 ==========

@router.get("/overview", summary="关键指标概览")
async def get_overview(
    period: Optional[str] = Query(None, description="月份 YYYY-MM，默认当前月"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取当月关键财务指标，含与上月对比和健康评分"""
    current_period = period or date.today().strftime("%Y-%m")
    prev_period = _prev_month(current_period)

    cur_start, cur_end = _month_range(current_period)
    prev_start, prev_end = _month_range(prev_period)

    # 本月收入支出
    cur_revenue, cur_expenses = await _compute_revenue_expense(db, cur_start, cur_end, book_id=current_book.id)
    cur_profit = cur_revenue - cur_expenses

    # 上月收入支出
    prev_revenue, prev_expenses = await _compute_revenue_expense(db, prev_start, prev_end, book_id=current_book.id)

    # 凭证数量统计
    voucher_stats_query = (
        select(
            Voucher.status,
            func.count(Voucher.id).label("cnt"),
        )
        .where(
            Voucher.voucher_date >= cur_start,
            Voucher.voucher_date <= cur_end,
            Voucher.book_id == current_book.id,
        )
        .group_by(Voucher.status)
    )
    voucher_result = await db.execute(voucher_stats_query)
    voucher_rows = voucher_result.all()

    voucher_count = 0
    pending_review_count = 0  # submitted 状态
    for row in voucher_rows:
        cnt = row.cnt
        voucher_count += cnt
        if row.status == "submitted":
            pending_review_count = cnt

    def _pct_change(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round((current - previous) / abs(previous) * 100, 2)

    # 健康评分
    health = await _calculate_health_score(db, current_period, cur_start, cur_end, book_id=current_book.id)

    return {
        "period": current_period,
        "total_revenue": round(cur_revenue, 2),
        "total_expenses": round(cur_expenses, 2),
        "net_profit": round(cur_profit, 2),
        "voucher_count": voucher_count,
        "pending_review_count": pending_review_count,
        "revenue_change_pct": _pct_change(cur_revenue, prev_revenue),
        "expenses_change_pct": _pct_change(cur_expenses, prev_expenses),
        "health_score": health["score"],
    }


@router.get("/trends", summary="收支趋势")
async def get_trends(
    months: int = Query(6, ge=1, le=36, description="统计月数"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取收入/支出/净利润月度趋势数据"""
    now = date.today()
    trend_data = []

    for i in range(months - 1, -1, -1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        target_month = f"{y}-{m:02d}"
        ms, me = _month_range(target_month)
        if date.fromisoformat(me) > now:
            me = now.isoformat()

        rev, exp = await _compute_revenue_expense(db, ms, me, book_id=current_book.id)
        trend_data.append({
            "month": target_month,
            "revenue": round(rev, 2),
            "expenses": round(exp, 2),
            "net_profit": round(rev - exp, 2),
        })

    return {"data": trend_data}


@router.get("/category-breakdown", summary="科目占比分析")
async def get_category_breakdown(
    period: Optional[str] = Query(None, description="月份 YYYY-MM"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取支出科目占比数据，用于饼图展示"""
    current_period = period or date.today().strftime("%Y-%m")
    start_date, end_date = _month_range(current_period)

    balances = await _get_account_balances(db, end_date, start_date, book_id=current_book.id)
    accounts = await _get_all_accounts(db, current_book.id)

    category_amounts = []

    for acc in accounts:
        if acc.account_type != "expense":
            continue
        bal = balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        if acc.balance_direction == "credit":
            amount = bal["total_credit"] - bal["total_debit"]
        else:
            amount = bal["total_debit"] - bal["total_credit"]

        if amount > 0:
            category_amounts.append({
                "account_code": acc.account_code,
                "account_name": acc.account_name,
                "amount": round(amount, 2),
            })

    category_amounts.sort(key=lambda x: x["amount"], reverse=True)

    total = sum(item["amount"] for item in category_amounts)
    result = []
    top10 = category_amounts[:10]

    for item in top10:
        result.append({
            "account_code": item["account_code"],
            "account_name": item["account_name"],
            "amount": item["amount"],
            "percentage": round(item["amount"] / total * 100, 2) if total > 0 else 0,
        })

    others = category_amounts[10:]
    if others:
        others_amount = sum(item["amount"] for item in others)
        if others_amount > 0:
            result.append({
                "account_code": "other",
                "account_name": "其他",
                "amount": round(others_amount, 2),
                "percentage": round(others_amount / total * 100, 2) if total > 0 else 0,
            })

    return {
        "period": current_period,
        "total": round(total, 2),
        "categories": result,
    }


@router.get("/monthly-comparison", summary="月度对比")
async def get_monthly_comparison(
    period: Optional[str] = Query(None, description="月份 YYYY-MM"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取本月、上月、去年同月的对比数据"""
    current_period = period or date.today().strftime("%Y-%m")
    prev_period = _prev_month(current_period)
    yoy_period = _prev_year_month(current_period)

    cur_start, cur_end = _month_range(current_period)
    prev_start, prev_end = _month_range(prev_period)
    yoy_start, yoy_end = _month_range(yoy_period)

    cur_rev, cur_exp = await _compute_revenue_expense(db, cur_start, cur_end, book_id=current_book.id)
    prev_rev, prev_exp = await _compute_revenue_expense(db, prev_start, prev_end, book_id=current_book.id)
    yoy_rev, yoy_exp = await _compute_revenue_expense(db, yoy_start, yoy_end, book_id=current_book.id)

    cur_profit = cur_rev - cur_exp
    prev_profit = prev_rev - prev_exp
    yoy_profit = yoy_rev - yoy_exp

    # 凭证数
    async def _count_vouchers(start, end):
        result = await db.execute(
            select(func.count(Voucher.id)).where(
                Voucher.voucher_date >= start,
                Voucher.voucher_date <= end,
                Voucher.book_id == current_book.id,
            )
        )
        return result.scalar() or 0

    cur_vc = await _count_vouchers(cur_start, cur_end)
    prev_vc = await _count_vouchers(prev_start, prev_end)
    yoy_vc = await _count_vouchers(yoy_start, yoy_end)

    def _pct(a, b):
        if b == 0:
            return None if a == 0 else 100.0
        return round((a - b) / abs(b) * 100, 2)

    return {
        "current": {
            "period": current_period,
            "revenue": round(cur_rev, 2),
            "expenses": round(cur_exp, 2),
            "net_profit": round(cur_profit, 2),
            "voucher_count": cur_vc,
        },
        "previous": {
            "period": prev_period,
            "revenue": round(prev_rev, 2),
            "expenses": round(prev_exp, 2),
            "net_profit": round(prev_profit, 2),
            "voucher_count": prev_vc,
        },
        "yoy": {
            "period": yoy_period,
            "revenue": round(yoy_rev, 2),
            "expenses": round(yoy_exp, 2),
            "net_profit": round(yoy_profit, 2),
            "voucher_count": yoy_vc,
        },
        "mom_change": {
            "revenue_pct": _pct(cur_rev, prev_rev),
            "expenses_pct": _pct(cur_exp, prev_exp),
            "net_profit_pct": _pct(cur_profit, prev_profit),
        },
        "yoy_change": {
            "revenue_pct": _pct(cur_rev, yoy_rev),
            "expenses_pct": _pct(cur_exp, yoy_exp),
            "net_profit_pct": _pct(cur_profit, yoy_profit),
        },
    }


async def _calculate_health_score(
    db: AsyncSession,
    current_period: str,
    cur_start: str,
    cur_end: str,
    book_id: Optional[int] = None,
) -> dict:
    """内部函数：计算财务健康评分"""
    prev_period = _prev_month(current_period)
    prev_start, prev_end = _month_range(prev_period)

    cur_revenue, cur_expenses = await _compute_revenue_expense(db, cur_start, cur_end, book_id=book_id)
    prev_revenue, _ = await _compute_revenue_expense(db, prev_start, prev_end, book_id=book_id)

    bs = await _compute_balance_sheet_totals(db, cur_end, book_id=book_id)

    def _safe_div(a, b):
        return a / b if b != 0 else 0

    # 1. 收入增长趋势 (30分)
    if prev_revenue > 0:
        revenue_growth = (cur_revenue - prev_revenue) / prev_revenue
        growth_score = min(30, max(0, 15 + revenue_growth * 30))
    else:
        revenue_growth = 0
        growth_score = 15 if cur_revenue > 0 else 15

    # 2. 利润率 (30分)
    if cur_revenue > 0:
        profit_margin = (cur_revenue - cur_expenses) / cur_revenue
        profit_score = min(30, max(0, profit_margin * 60))
    else:
        profit_margin = 0
        profit_score = 15

    # 3. 费用控制 (20分)
    if cur_revenue > 0:
        expense_ratio = cur_expenses / cur_revenue
        expense_score = min(20, max(0, (1 - expense_ratio) * 20))
    else:
        expense_ratio = 0
        expense_score = 10

    # 4. 资产负债率 (20分)
    debt_ratio = _safe_div(bs["total_liabilities"], bs["total_assets"])
    if debt_ratio <= 0.5:
        debt_score = 20
    elif debt_ratio <= 1:
        debt_score = max(0, 20 - (debt_ratio - 0.5) * 40)
    else:
        debt_score = 0

    total_score = round(growth_score + profit_score + expense_score + debt_score, 2)

    # 无数据时默认50分
    if cur_revenue == 0 and cur_expenses == 0:
        total_score = 50.0
        growth_score = 15.0
        profit_score = 15.0
        expense_score = 10.0
        debt_score = 10.0

    # 生成建议
    suggestions = []
    if revenue_growth < 0:
        suggestions.append("收入同比下降，建议关注市场拓展和客户增长")
    if profit_margin < 0.1:
        suggestions.append("利润率偏低，建议优化成本结构和定价策略")
    if expense_ratio > 0.7:
        suggestions.append("费用占比过高，建议审查各项费用支出")
    if debt_ratio > 0.6:
        suggestions.append("负债率偏高，建议控制负债规模")
    if total_score >= 80:
        suggestions.append("经营状况良好，保持当前管理策略")
    if not suggestions:
        suggestions.append("各项指标平稳，暂无特别建议")

    return {
        "score": total_score,
        "period": current_period,
        "breakdown": {
            "revenue_growth": {
                "label": "收入增长趋势",
                "score": round(growth_score, 2),
                "value": round(revenue_growth * 100, 2),
                "weight": 30,
                "description": f"收入环比变化 {round(revenue_growth * 100, 2)}%",
            },
            "profit_margin": {
                "label": "利润率",
                "score": round(profit_score, 2),
                "value": round(profit_margin * 100, 2),
                "weight": 30,
                "description": f"净利润率 {round(profit_margin * 100, 2)}%",
            },
            "expense_control": {
                "label": "费用控制",
                "score": round(expense_score, 2),
                "value": round(expense_ratio * 100, 2),
                "weight": 20,
                "description": f"费用占比 {round(expense_ratio * 100, 2)}%",
            },
            "debt_ratio": {
                "label": "资产负债率",
                "score": round(debt_score, 2),
                "value": round(debt_ratio * 100, 2),
                "weight": 20,
                "description": f"资产负债率 {round(debt_ratio * 100, 2)}%",
            },
        },
        "suggestions": suggestions,
    }


@router.get("/health-score", summary="财务健康评分")
async def get_health_score(
    period: Optional[str] = Query(None, description="月份 YYYY-MM"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """计算财务健康评分 (0-100)"""
    current_period = period or date.today().strftime("%Y-%m")
    cur_start, cur_end = _month_range(current_period)
    return await _calculate_health_score(db, current_period, cur_start, cur_end, book_id=current_book.id)


@router.get("/recent-vouchers", summary="最近凭证")
async def get_recent_vouchers(
    limit: int = Query(5, ge=1, le=20, description="返回条数"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取最近凭证列表"""
    result = await db.execute(
        select(Voucher)
        .where(Voucher.book_id == current_book.id)
        .order_by(Voucher.voucher_date.desc(), Voucher.updated_at.desc())
        .limit(limit)
    )
    vouchers = result.scalars().all()

    items = []
    for v in vouchers:
        items.append({
            "id": v.id,
            "voucher_no": v.voucher_no,
            "voucher_date": v.voucher_date.isoformat() if v.voucher_date else "",
            "summary": v.summary,
            "status": v.status,
            "debit_total": 0,
            "credit_total": 0,
        })

    # 批量加载分录金额
    if items:
        v_ids = [it["id"] for it in items]
        item_result = await db.execute(
            select(
                VoucherItem.voucher_id,
                func.sum(VoucherItem.debit_amount).label("total_debit"),
                func.sum(VoucherItem.credit_amount).label("total_credit"),
            )
            .where(VoucherItem.voucher_id.in_(v_ids))
            .group_by(VoucherItem.voucher_id)
        )
        item_rows = item_result.all()
        v_map = {row.voucher_id: (float(row.total_debit or 0), float(row.total_credit or 0)) for row in item_rows}
        for it in items:
            if it["id"] in v_map:
                it["debit_total"] = round(v_map[it["id"]][0], 2)
                it["credit_total"] = round(v_map[it["id"]][1], 2)

    return {"vouchers": items}


# ========== 工作看板 ==========

class WorkbenchTaskItem(BaseModel):
    """看板任务项"""
    id: int
    type: str  # voucher / invoice / asset / gap
    title: str
    subtitle: str = ""
    status: str = ""
    status_label: str = ""
    status_type: str = ""  # info / warning / danger / success
    date: str = ""
    amount: float = 0
    link: str = ""
    raw_data: dict = Field(default_factory=dict)


class WorkbenchResponse(BaseModel):
    """工作看板响应"""
    # 统计卡片
    pending_review_count: int = 0
    pending_cashier_review_count: int = 0
    pending_approval_count: int = 0
    pending_post_count: int = 0
    gap_count: int = 0
    pending_invoice_count: int = 0
    carry_forward_needed: bool = False
    pending_depreciation_count: int = 0

    # 看板列（每列最多20条）
    pending_review_tasks: list[WorkbenchTaskItem] = Field(default_factory=list)
    pending_cashier_review_tasks: list[WorkbenchTaskItem] = Field(default_factory=list)
    pending_approval_tasks: list[WorkbenchTaskItem] = Field(default_factory=list)
    pending_post_tasks: list[WorkbenchTaskItem] = Field(default_factory=list)


CASH_BANK_CODES = ("1001", "1002", "1012")  # 现金/银行存款/其他货币资金

STATUS_LABELS = {
    "draft": "草稿",
    "submitted": "已提交",
    "cashier_reviewed": "出纳已复核",
    "reviewed": "已审核",
    "approved": "已审批",
    "posted": "已过账",
}

STATUS_TYPES = {
    "draft": "info",
    "submitted": "warning",
    "cashier_reviewed": "",
    "reviewed": "primary",
    "approved": "success",
    "posted": "",
}


@router.get("/workbench", response_model=WorkbenchResponse, summary="工作看板")
async def get_workbench(
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取工作看板数据：待办统计 + 看板任务列表"""
    book_id = current_book.id

    # 1. 按状态统计凭证
    status_query = (
        select(Voucher.status, func.count(Voucher.id))
        .where(Voucher.book_id == book_id)
        .group_by(Voucher.status)
    )
    status_result = await db.execute(status_query)
    status_counts = dict(status_result.all())

    pending_review_count = status_counts.get("submitted", 0)
    pending_approval_count = status_counts.get("reviewed", 0)
    pending_post_count = status_counts.get("approved", 0)

    # 2. 待出纳复核：submitted 状态 + 涉及现金/银行科目
    cashier_query = (
        select(func.count(func.distinct(Voucher.id)))
        .join(VoucherItem, VoucherItem.voucher_id == Voucher.id)
        .where(
            Voucher.book_id == book_id,
            Voucher.status == "submitted",
            func.substr(VoucherItem.account_code, 1, 4).in_(CASH_BANK_CODES),
        )
    )
    cashier_result = await db.execute(cashier_query)
    pending_cashier_review_count = cashier_result.scalar() or 0

    # 3. 凭证断号检测（仅检查新格式凭证：记/转/收/付-YYYY-MM-XXX）
    gap_count = 0
    gap_query = (
        select(
            Voucher.voucher_type,
            func.cast(func.substr(Voucher.voucher_no, -3), Integer).label("seq_num"),
        )
        .where(
            Voucher.book_id == book_id,
            Voucher.voucher_type.in_(["记", "转", "收", "付"]),
        )
        .order_by(Voucher.voucher_type, "seq_num")
    )
    gap_result = await db.execute(gap_query)
    gap_rows = gap_result.all()
    if gap_rows:
        # 按凭证字分组
        groups = {}
        for row in gap_rows:
            groups.setdefault(row.voucher_type, []).append(row.seq_num)
        for vt, seqs in groups.items():
            seqs.sort()
            for i in range(1, len(seqs)):
                if seqs[i] - seqs[i - 1] > 1:
                    gap_count += seqs[i] - seqs[i - 1] - 1

    # 4. 待处理发票
    invoice_result = await db.execute(
        select(func.count(Invoice.id)).where(
            Invoice.book_id == book_id,
            Invoice.status == "pending",
        )
    )
    pending_invoice_count = invoice_result.scalar() or 0

    # 5. 期末结转检查：当月是否有结转凭证
    now = date.today()
    current_month_start = now.replace(day=1).isoformat()
    cf_result = await db.execute(
        select(func.count(Voucher.id)).where(
            Voucher.book_id == book_id,
            Voucher.voucher_date >= current_month_start,
            Voucher.summary.like("%结转%"),
        )
    )
    cf_count = cf_result.scalar() or 0
    carry_forward_needed = cf_count == 0

    # 6. 固定资产待折旧
    depr_result = await db.execute(
        select(func.count(FixedAsset.id)).where(
            FixedAsset.book_id == book_id,
            FixedAsset.status == "in_use",
        )
    )
    pending_depreciation_count = depr_result.scalar() or 0

    # 7. 构建看板任务列表
    async def _build_voucher_tasks(status: str, limit: int = 20) -> list[WorkbenchTaskItem]:
        query = (
            select(Voucher)
            .where(Voucher.book_id == book_id, Voucher.status == status)
            .order_by(Voucher.voucher_date.desc(), Voucher.voucher_no.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        vouchers = result.scalars().all()

        tasks = []
        for v in vouchers:
            # 获取分录金额
            item_result = await db.execute(
                select(
                    func.sum(VoucherItem.debit_amount).label("total_debit"),
                    func.sum(VoucherItem.credit_amount).label("total_credit"),
                ).where(VoucherItem.voucher_id == v.id)
            )
            item_row = item_result.first()
            total_debit = float(item_row.total_debit or 0)

            link = f"/voucher/{v.id}/edit"
            if status == "submitted":
                link = f"/voucher/{v.id}/review"
            elif status == "approved":
                link = f"/voucher/list"

            tasks.append(WorkbenchTaskItem(
                id=v.id,
                type="voucher",
                title=v.voucher_no or "",
                subtitle=v.summary or "",
                status=status,
                status_label=STATUS_LABELS.get(status, status),
                status_type=STATUS_TYPES.get(status, ""),
                date=v.voucher_date.isoformat() if v.voucher_date else "",
                amount=round(total_debit, 2),
                link=link,
                raw_data={
                    "voucher_type": v.voucher_type,
                    "created_by": getattr(v, "created_by", None),
                },
            ))
        return tasks

    # 现金/银行凭证的待出纳复核
    async def _build_cashier_tasks(limit: int = 20) -> list[WorkbenchTaskItem]:
        query = (
            select(Voucher)
            .join(VoucherItem, VoucherItem.voucher_id == Voucher.id)
            .where(
                Voucher.book_id == book_id,
                Voucher.status == "submitted",
                func.substr(VoucherItem.account_code, 1, 4).in_(CASH_BANK_CODES),
            )
            .distinct()
            .order_by(Voucher.voucher_date.desc(), Voucher.voucher_no.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        vouchers = result.scalars().all()

        tasks = []
        for v in vouchers:
            item_result = await db.execute(
                select(func.sum(VoucherItem.debit_amount).label("total_debit"))
                .where(VoucherItem.voucher_id == v.id)
            )
            item_row = item_result.first()
            total_debit = float(item_row.total_debit or 0)

            tasks.append(WorkbenchTaskItem(
                id=v.id,
                type="voucher",
                title=v.voucher_no or "",
                subtitle=v.summary or "",
                status="submitted",
                status_label="待出纳复核",
                status_type="warning",
                date=v.voucher_date.isoformat() if v.voucher_date else "",
                amount=round(total_debit, 2),
                link=f"/voucher/{v.id}/review",
                raw_data={"voucher_type": v.voucher_type},
            ))
        return tasks

    pending_review_tasks = await _build_voucher_tasks("submitted")
    pending_cashier_review_tasks = await _build_cashier_tasks()
    pending_approval_tasks = await _build_voucher_tasks("reviewed")
    pending_post_tasks = await _build_voucher_tasks("approved")

    return WorkbenchResponse(
        pending_review_count=pending_review_count,
        pending_cashier_review_count=pending_cashier_review_count,
        pending_approval_count=pending_approval_count,
        pending_post_count=pending_post_count,
        gap_count=gap_count,
        pending_invoice_count=pending_invoice_count,
        carry_forward_needed=carry_forward_needed,
        pending_depreciation_count=pending_depreciation_count,
        pending_review_tasks=pending_review_tasks,
        pending_cashier_review_tasks=pending_cashier_review_tasks,
        pending_approval_tasks=pending_approval_tasks,
        pending_post_tasks=pending_post_tasks,
    )