"""
报表 API 路由
提供财务报表生成和导出功能
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.voucher import Voucher, VoucherItem, Account
from auth.middleware import get_current_user, require_permission
from auth.book_context import get_current_book
from utils.data_mask import mask_report_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["报表"])


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


async def _get_account_balances(
    db: AsyncSession,
    end_date: str,
    start_date: Optional[str] = None,
    book_id: Optional[int] = None,
) -> dict:
    """获取各科目的余额汇总"""
    # 查询 end_date 之前所有已审核通过的凭证分录
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


# ========== API 端点 ==========

@router.get("/balance-sheet", summary="资产负债表")
async def get_balance_sheet(
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取资产负债表"""
    start_date, end_date = _month_range(period)
    logger.info(f"用户 {current_user.username} 请求资产负债表: {start_date} ~ {end_date}")

    accounts = await _get_all_accounts(db, current_book.id)
    balances = await _get_account_balances(db, end_date, book_id=current_book.id)

    assets = []
    liabilities = []
    equity = []
    total_assets = 0.0
    total_liabilities = 0.0
    total_equity = 0.0

    for acc in accounts:
        code = acc.account_code
        bal = balances.get(code, {"total_debit": 0, "total_credit": 0})
        # 根据余额方向计算期末余额
        if acc.balance_direction == "debit":
            ending = bal["total_debit"] - bal["total_credit"]
        else:
            ending = bal["total_credit"] - bal["total_debit"]

        item = {
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "ending_balance": round(ending, 2),
        }

        if acc.account_type in ("asset",):
            assets.append(item)
            total_assets += ending
        elif acc.account_type in ("liability",):
            liabilities.append(item)
            total_liabilities += ending
        elif acc.account_type in ("equity",):
            equity.append(item)
            total_equity += ending

    return mask_report_response({
        "report_date": end_date,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": round(total_assets, 2),
        "total_liabilities": round(total_liabilities, 2),
        "total_equity": round(total_equity, 2),
        "total_liabilities_and_equity": round(total_liabilities + total_equity, 2),
    }, current_user.role)


@router.get("/income-statement", summary="利润表")
async def get_income_statement(
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取利润表"""
    start_date, end_date = _month_range(period)
    logger.info(f"用户 {current_user.username} 请求利润表: {start_date} ~ {end_date}")

    # 本月数据
    month_balances = await _get_account_balances(db, end_date, start_date, book_id=current_book.id)
    # 本年累计（从年初到 end_date）
    year_start = f"{end_date[:4]}-01-01"
    year_balances = await _get_account_balances(db, end_date, year_start, book_id=current_book.id)

    accounts = await _get_all_accounts(db, current_book.id)

    revenue_items = []
    expense_items = []
    total_revenue = 0.0
    total_expenses = 0.0

    for acc in accounts:
        if acc.account_type not in ("revenue", "expense"):
            continue

        month_bal = month_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        year_bal = year_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})

        if acc.balance_direction == "credit":
            month_amount = month_bal["total_credit"] - month_bal["total_debit"]
            year_amount = year_bal["total_credit"] - year_bal["total_debit"]
        else:
            month_amount = month_bal["total_debit"] - month_bal["total_credit"]
            year_amount = year_bal["total_debit"] - year_bal["total_credit"]

        item = {
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "current_amount": round(month_amount, 2),
            "cumulative_amount": round(year_amount, 2),
        }

        if acc.account_type == "revenue":
            revenue_items.append(item)
            total_revenue += month_amount
        else:
            expense_items.append(item)
            total_expenses += month_amount

    return mask_report_response({
        "start_date": start_date,
        "end_date": end_date,
        "revenue": revenue_items,
        "expenses": expense_items,
        "total_revenue": round(total_revenue, 2),
        "total_expenses": round(total_expenses, 2),
        "net_profit": round(total_revenue - total_expenses, 2),
    }, current_user.role)


@router.get("/cash-flow", summary="现金流量表")
async def get_cash_flow(
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取现金流量表"""
    start_date, end_date = _month_range(period)
    logger.info(f"用户 {current_user.username} 请求现金流量表: {start_date} ~ {end_date}")

    # 现金类科目编码前缀
    cash_prefixes = ("1001", "1002", "1012", "1101")

    # 分类关键词
    operating_keywords = [
        '销售', '采购', '工资', '税费', '报销', '费用', '日常', '经营',
        '收入', '成本', '维修', '办公', '差旅', '水电', '租金', '广告', '运费',
    ]
    investing_keywords = [
        '固定资产', '购建', '处置', '投资', '股权', '债券', '理财', '设备', '厂房', '建设',
    ]
    financing_keywords = [
        '借款', '贷款', '还款', '融资', '分红', '股利', '增资', '减资', '利息支出',
    ]

    def _classify_cash_flow(summary: str) -> str:
        """根据凭证摘要关键词分类"""
        if not summary:
            return "operating"
        for kw in investing_keywords:
            if kw in summary:
                return "investing"
        for kw in financing_keywords:
            if kw in summary:
                return "financing"
        for kw in operating_keywords:
            if kw in summary:
                return "operating"
        return "operating"

    # 查询指定期间内所有 reviewed/posted 状态的凭证条目，关联凭证摘要
    query = (
        select(
            VoucherItem.account_code,
            VoucherItem.account_name,
            VoucherItem.debit_amount,
            VoucherItem.credit_amount,
            VoucherItem.description,
            Voucher.summary,
            Voucher.voucher_no,
            Voucher.voucher_date,
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            Voucher.status.in_(["reviewed", "posted"]),
            Voucher.voucher_date >= start_date,
            Voucher.voucher_date <= end_date,
            Voucher.book_id == current_book.id,
        )
        .order_by(Voucher.voucher_date, Voucher.voucher_no)
    )

    result = await db.execute(query)
    rows = result.all()

    operating_inflow = []
    operating_outflow = []
    investing_inflow = []
    investing_outflow = []
    financing_inflow = []
    financing_outflow = []

    for row in rows:
        code = row.account_code
        if not code.startswith(cash_prefixes):
            continue

        category = _classify_cash_flow(row.summary or "")
        debit = float(row.debit_amount or 0)
        credit = float(row.credit_amount or 0)

        # 现金科目：借方 = 流入，贷方 = 流出
        if debit > 0:
            item = {
                "voucher_no": row.voucher_no,
                "voucher_date": str(row.voucher_date),
                "account_code": code,
                "account_name": row.account_name,
                "summary": row.summary,
                "description": row.description,
                "amount": round(debit, 2),
            }
            if category == "investing":
                investing_inflow.append(item)
            elif category == "financing":
                financing_inflow.append(item)
            else:
                operating_inflow.append(item)

        if credit > 0:
            item = {
                "voucher_no": row.voucher_no,
                "voucher_date": str(row.voucher_date),
                "account_code": code,
                "account_name": row.account_name,
                "summary": row.summary,
                "description": row.description,
                "amount": round(credit, 2),
            }
            if category == "investing":
                investing_outflow.append(item)
            elif category == "financing":
                financing_outflow.append(item)
            else:
                operating_outflow.append(item)

    # 计算净额
    operating_net = round(
        sum(i["amount"] for i in operating_inflow) - sum(i["amount"] for i in operating_outflow), 2
    )
    investing_net = round(
        sum(i["amount"] for i in investing_inflow) - sum(i["amount"] for i in investing_outflow), 2
    )
    financing_net = round(
        sum(i["amount"] for i in financing_inflow) - sum(i["amount"] for i in financing_outflow), 2
    )
    net_cash_flow = round(operating_net + investing_net + financing_net, 2)

    return mask_report_response({
        "start_date": start_date,
        "end_date": end_date,
        "operating": {
            "inflow": operating_inflow,
            "outflow": operating_outflow,
            "net": operating_net,
        },
        "investing": {
            "inflow": investing_inflow,
            "outflow": investing_outflow,
            "net": investing_net,
        },
        "financing": {
            "inflow": financing_inflow,
            "outflow": financing_outflow,
            "net": financing_net,
        },
        "net_cash_flow": net_cash_flow,
    }, current_user.role)


@router.get("/account-ledger", summary="科目余额表")
async def get_account_ledger(
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取科目余额表"""
    start_date, end_date = _month_range(period)
    logger.info(f"用户 {current_user.username} 请求科目余额表: {start_date} ~ {end_date}")

    # 期初余额（start_date 之前）
    day_before = (date.fromisoformat(start_date) - timedelta(days=1)).isoformat()
    opening_balances = await _get_account_balances(db, day_before, book_id=current_book.id)
    # 本期发生额
    period_balances = await _get_account_balances(db, end_date, start_date, book_id=current_book.id)

    accounts = await _get_all_accounts(db, current_book.id)
    items = []

    for acc in accounts:
        opening = opening_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        period = period_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})

        # 期初余额
        if acc.balance_direction == "debit":
            beginning_debit = opening["total_debit"] - opening["total_credit"]
            beginning_credit = 0.0
        else:
            beginning_debit = 0.0
            beginning_credit = opening["total_credit"] - opening["total_debit"]

        # 本期发生额
        current_debit = period["total_debit"]
        current_credit = period["total_credit"]

        # 期末余额
        ending_debit = beginning_debit + current_debit
        ending_credit = beginning_credit + current_credit

        if acc.balance_direction == "debit":
            net_ending = ending_debit - ending_credit
            ending_debit = max(0, net_ending)
            ending_credit = max(0, -net_ending)
        else:
            net_ending = ending_credit - ending_debit
            ending_credit = max(0, net_ending)
            ending_debit = max(0, -net_ending)

        items.append({
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "beginning_debit": round(beginning_debit, 2),
            "beginning_credit": round(beginning_credit, 2),
            "current_debit": round(current_debit, 2),
            "current_credit": round(current_credit, 2),
            "ending_debit": round(ending_debit, 2),
            "ending_credit": round(ending_credit, 2),
        })

    return mask_report_response({
        "start_date": start_date,
        "end_date": end_date,
        "items": items,
    }, current_user.role)


@router.get("/general-ledger", summary="总账")
async def get_general_ledger(
    account_code: Optional[str] = Query(None, description="科目代码"),
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取总账——按科目汇总期初余额、本期发生额和期末余额"""
    logger.info(
        f"用户 {current_user.username} 请求总账: {start_date} ~ {end_date}"
    )

    day_before = (date.fromisoformat(start_date) - timedelta(days=1)).isoformat()

    # 期初余额（start_date 之前）
    opening_balances = await _get_account_balances(db, day_before, book_id=current_book.id)
    # 本期发生额
    period_balances = await _get_account_balances(db, end_date, start_date, book_id=current_book.id)

    accounts = await _get_all_accounts(db, current_book.id)

    all_items = []
    for acc in accounts:
        if account_code and not acc.account_code.startswith(account_code):
            continue

        opening = opening_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        period = period_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})

        # 期初余额：根据余额方向计算
        if acc.balance_direction == "debit":
            opening_balance = opening["total_debit"] - opening["total_credit"]
        else:
            opening_balance = opening["total_credit"] - opening["total_debit"]

        current_debit = period["total_debit"]
        current_credit = period["total_credit"]

        # 期末余额 = 期初余额 + 本期借方 - 本期贷方（按余额方向调整）
        if acc.balance_direction == "debit":
            ending_balance = opening_balance + current_debit - current_credit
        else:
            ending_balance = opening_balance + current_credit - current_debit

        all_items.append({
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "balance_direction": acc.balance_direction,
            "opening_balance": round(opening_balance, 2),
            "current_debit": round(current_debit, 2),
            "current_credit": round(current_credit, 2),
            "ending_balance": round(ending_balance, 2),
        })

    total = len(all_items)
    start = (page - 1) * page_size
    items = all_items[start:start + page_size]

    return mask_report_response({
        "start_date": start_date,
        "end_date": end_date,
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }, current_user.role)


@router.get("/subsidiary-ledger", summary="明细账")
async def get_subsidiary_ledger(
    account_code: str = Query(..., description="科目代码"),
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取明细账——指定科目在指定期间内的所有凭证分录明细"""
    logger.info(
        f"用户 {current_user.username} 请求明细账: {account_code} {start_date} ~ {end_date}"
    )

    day_before = (date.fromisoformat(start_date) - timedelta(days=1)).isoformat()

    # 期初余额
    opening_balances = await _get_account_balances(db, day_before, book_id=current_book.id)
    opening = opening_balances.get(account_code, {"total_debit": 0, "total_credit": 0})

    # 获取科目信息确定余额方向
    acc_result = await db.execute(
        select(Account).where(
            Account.account_code == account_code,
            Account.is_active == True,
            Account.book_id == current_book.id,
        )
    )
    account = acc_result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"科目不存在: {account_code}",
        )

    if account.balance_direction == "debit":
        opening_balance = opening["total_debit"] - opening["total_credit"]
    else:
        opening_balance = opening["total_credit"] - opening["total_debit"]

    # 查询本期所有凭证分录（先查总数用于分页）
    base_query = (
        select(VoucherItem)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            Voucher.status.in_(["reviewed", "posted"]),
            Voucher.voucher_date >= start_date,
            Voucher.voucher_date <= end_date,
            Voucher.book_id == current_book.id,
            VoucherItem.account_code == account_code,
        )
    )

    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 查询本期数据（不带分页先获取全部，用于计算余额）
    detail_query = (
        select(
            VoucherItem,
            Voucher.voucher_date,
            Voucher.voucher_no,
            Voucher.summary,
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            Voucher.status.in_(["reviewed", "posted"]),
            Voucher.voucher_date >= start_date,
            Voucher.voucher_date <= end_date,
            Voucher.book_id == current_book.id,
            VoucherItem.account_code == account_code,
        )
        .order_by(Voucher.voucher_date, Voucher.voucher_no, VoucherItem.id)
    )

    detail_result = await db.execute(detail_query)
    all_rows = detail_result.all()

    # 逐行计算余额
    running_balance = opening_balance
    items = []
    period_debit = 0.0
    period_credit = 0.0

    for row in all_rows:
        item = row[0]
        debit = float(item.debit_amount or 0)
        credit = float(item.credit_amount or 0)

        if account.balance_direction == "debit":
            running_balance = running_balance + debit - credit
        else:
            running_balance = running_balance + credit - debit

        period_debit += debit
        period_credit += credit

        items.append({
            "voucher_date": str(row[1]),
            "voucher_no": row[2],
            "summary": row[3],
            "description": item.description,
            "debit_amount": round(debit, 2),
            "credit_amount": round(credit, 2),
            "balance": round(running_balance, 2),
        })

    # 分页截取
    start_idx = (page - 1) * page_size
    paged_items = items[start_idx:start_idx + page_size]

    return mask_report_response({
        "account_code": account_code,
        "account_name": account.account_name,
        "balance_direction": account.balance_direction,
        "start_date": start_date,
        "end_date": end_date,
        "opening_balance": round(opening_balance, 2),
        "period_debit": round(period_debit, 2),
        "period_credit": round(period_credit, 2),
        "ending_balance": round(running_balance, 2),
        "items": paged_items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }, current_user.role)


@router.get("/journal", summary="日记账")
async def get_journal(
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
    account_type: Optional[str] = Query(None, description="科目类型: cash/bank"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取日记账——现金和银行存款科目的凭证分录"""
    logger.info(
        f"用户 {current_user.username} 请求日记账: {start_date} ~ {end_date}, account_type={account_type}"
    )

    # 确定科目代码范围
    if account_type == "cash":
        account_codes = ["1001"]
    elif account_type == "bank":
        account_codes = ["1002"]
    else:
        account_codes = ["1001", "1002"]

    # 查询总数
    count_query = (
        select(func.count())
        .select_from(VoucherItem)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            Voucher.status.in_(["reviewed", "posted"]),
            Voucher.voucher_date >= start_date,
            Voucher.voucher_date <= end_date,
            Voucher.book_id == current_book.id,
            VoucherItem.account_code.in_(account_codes),
        )
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 查询数据
    query = (
        select(
            VoucherItem,
            Voucher.voucher_date,
            Voucher.voucher_no,
            Voucher.summary,
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            Voucher.status.in_(["reviewed", "posted"]),
            Voucher.voucher_date >= start_date,
            Voucher.voucher_date <= end_date,
            Voucher.book_id == current_book.id,
            VoucherItem.account_code.in_(account_codes),
        )
        .order_by(Voucher.voucher_date, Voucher.voucher_no, VoucherItem.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    rows = result.all()

    items = []
    total_debit = 0.0
    total_credit = 0.0

    for row in rows:
        item = row[0]
        debit = float(item.debit_amount or 0)
        credit = float(item.credit_amount or 0)
        total_debit += debit
        total_credit += credit

        items.append({
            "voucher_date": str(row[1]),
            "voucher_no": row[2],
            "summary": row[3],
            "description": item.description,
            "account_code": item.account_code,
            "account_name": item.account_name,
            "debit_amount": round(debit, 2),
            "credit_amount": round(credit, 2),
        })

    return mask_report_response({
        "start_date": start_date,
        "end_date": end_date,
        "account_type": account_type or "all",
        "items": items,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "total": total,
        "page": page,
        "page_size": page_size,
    }, current_user.role)


@router.get("/trial-balance", summary="科目余额表")
async def get_trial_balance(
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    account_type: Optional[str] = Query(None, description="科目类型筛选"),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取科目余额表（含科目类型和余额方向）"""
    start_date, end_date = _month_range(period)
    logger.info(
        f"用户 {current_user.username} 请求科目余额表: {start_date} ~ {end_date}, "
        f"account_type={account_type}"
    )

    # 期初余额（start_date 之前）
    day_before = (date.fromisoformat(start_date) - timedelta(days=1)).isoformat()
    opening_balances = await _get_account_balances(db, day_before, book_id=current_book.id)
    # 本期发生额
    period_balances = await _get_account_balances(db, end_date, start_date, book_id=current_book.id)

    accounts = await _get_all_accounts(db, current_book.id)

    # 按科目类型筛选
    if account_type:
        accounts = [a for a in accounts if a.account_type == account_type]

    items = []
    for acc in accounts:
        opening = opening_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        period = period_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})

        # 期初余额
        if acc.balance_direction == "debit":
            beginning_debit = opening["total_debit"] - opening["total_credit"]
            beginning_credit = 0.0
        else:
            beginning_debit = 0.0
            beginning_credit = opening["total_credit"] - opening["total_debit"]

        # 本期发生额
        current_debit = period["total_debit"]
        current_credit = period["total_credit"]

        # 期末余额
        ending_debit = beginning_debit + current_debit
        ending_credit = beginning_credit + current_credit

        if acc.balance_direction == "debit":
            net_ending = ending_debit - ending_credit
            ending_debit = max(0, net_ending)
            ending_credit = max(0, -net_ending)
        else:
            net_ending = ending_credit - ending_debit
            ending_credit = max(0, net_ending)
            ending_debit = max(0, -net_ending)

        items.append({
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "account_type": acc.account_type,
            "balance_direction": acc.balance_direction,
            "beginning_debit": round(beginning_debit, 2),
            "beginning_credit": round(beginning_credit, 2),
            "current_debit": round(current_debit, 2),
            "current_credit": round(current_credit, 2),
            "ending_debit": round(ending_debit, 2),
            "ending_credit": round(ending_credit, 2),
        })

    return mask_report_response({
        "start_date": start_date,
        "end_date": end_date,
        "items": items,
    }, current_user.role)


@router.get("/trial-balance-summary", summary="试算平衡表")
async def get_trial_balance_summary(
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取试算平衡表（汇总所有科目余额并检查平衡）"""
    start_date, end_date = _month_range(period)
    logger.info(f"用户 {current_user.username} 请求试算平衡表: {start_date} ~ {end_date}")

    # 期初余额（start_date 之前）
    day_before = (date.fromisoformat(start_date) - timedelta(days=1)).isoformat()
    opening_balances = await _get_account_balances(db, day_before, book_id=current_book.id)
    # 本期发生额
    period_balances = await _get_account_balances(db, end_date, start_date, book_id=current_book.id)

    accounts = await _get_all_accounts(db, current_book.id)

    total_beginning_debit = 0.0
    total_beginning_credit = 0.0
    total_current_debit = 0.0
    total_current_credit = 0.0
    total_ending_debit = 0.0
    total_ending_credit = 0.0

    items = []
    for acc in accounts:
        opening = opening_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        period = period_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})

        # 期初余额
        if acc.balance_direction == "debit":
            beginning_debit = opening["total_debit"] - opening["total_credit"]
            beginning_credit = 0.0
        else:
            beginning_debit = 0.0
            beginning_credit = opening["total_credit"] - opening["total_debit"]

        beginning_debit = max(0, beginning_debit)
        beginning_credit = max(0, beginning_credit)

        # 本期发生额
        current_debit = period["total_debit"]
        current_credit = period["total_credit"]

        # 期末余额
        ending_debit = beginning_debit + current_debit
        ending_credit = beginning_credit + current_credit

        if acc.balance_direction == "debit":
            net_ending = ending_debit - ending_credit
            ending_debit = max(0, net_ending)
            ending_credit = max(0, -net_ending)
        else:
            net_ending = ending_credit - ending_debit
            ending_credit = max(0, net_ending)
            ending_debit = max(0, -net_ending)

        total_beginning_debit += beginning_debit
        total_beginning_credit += beginning_credit
        total_current_debit += current_debit
        total_current_credit += current_credit
        total_ending_debit += ending_debit
        total_ending_credit += ending_credit

        items.append({
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "account_type": acc.account_type,
            "balance_direction": acc.balance_direction,
            "beginning_debit": round(beginning_debit, 2),
            "beginning_credit": round(beginning_credit, 2),
            "current_debit": round(current_debit, 2),
            "current_credit": round(current_credit, 2),
            "ending_debit": round(ending_debit, 2),
            "ending_credit": round(ending_credit, 2),
        })

    # 计算平衡状态
    beginning_balanced = abs(total_beginning_debit - total_beginning_credit) < 0.01
    current_balanced = abs(total_current_debit - total_current_credit) < 0.01
    ending_balanced = abs(total_ending_debit - total_ending_credit) < 0.01
    is_balanced = beginning_balanced and current_balanced and ending_balanced

    return mask_report_response({
        "start_date": start_date,
        "end_date": end_date,
        "items": items,
        "summary": {
            "total_beginning_debit": round(total_beginning_debit, 2),
            "total_beginning_credit": round(total_beginning_credit, 2),
            "total_current_debit": round(total_current_debit, 2),
            "total_current_credit": round(total_current_credit, 2),
            "total_ending_debit": round(total_ending_debit, 2),
            "total_ending_credit": round(total_ending_credit, 2),
        },
        "balance_check": {
            "beginning_balanced": beginning_balanced,
            "current_balanced": current_balanced,
            "ending_balanced": ending_balanced,
            "is_balanced": is_balanced,
            "beginning_diff": round(total_beginning_debit - total_beginning_credit, 2),
            "current_diff": round(total_current_debit - total_current_credit, 2),
            "ending_diff": round(total_ending_debit - total_ending_credit, 2),
        },
    }, current_user.role)


@router.get("/comparison", summary="多期间对比报表")
async def get_comparison(
    report_type: str = Query(..., description="报表类型: balance-sheet / income-statement"),
    periods: str = Query(..., description="逗号分隔的期间列表，格式 YYYY-MM"),
    compare_type: str = Query("monthly", description="对比类型: monthly / quarterly / yearly"),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取多期间对比数据"""
    valid_types = {"balance-sheet", "income-statement"}
    if report_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的报表类型，有效类型: {', '.join(valid_types)}",
        )

    period_list = [p.strip() for p in periods.split(",") if p.strip()]
    if not period_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少提供一个期间",
        )

    logger.info(
        f"用户 {current_user.username} 请求多期间对比: {report_type}, "
        f"periods={periods}, compare_type={compare_type}"
    )

    accounts = await _get_all_accounts(db, current_book.id)
    result_periods = []

    for period in period_list:
        start_date, end_date = _month_range(period)
        balances = await _get_account_balances(db, end_date, book_id=current_book.id)

        if report_type == "balance-sheet":
            total_assets = 0.0
            total_liabilities = 0.0
            total_equity = 0.0

            for acc in accounts:
                bal = balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
                if acc.balance_direction == "debit":
                    ending = bal["total_debit"] - bal["total_credit"]
                else:
                    ending = bal["total_credit"] - bal["total_debit"]

                if acc.account_type in ("asset",):
                    total_assets += ending
                elif acc.account_type in ("liability",):
                    total_liabilities += ending
                elif acc.account_type in ("equity",):
                    total_equity += ending

            result_periods.append({
                "period": period,
                "total_assets": round(total_assets, 2),
                "total_liabilities": round(total_liabilities, 2),
                "total_equity": round(total_equity, 2),
                "total_liabilities_and_equity": round(total_liabilities + total_equity, 2),
            })

        elif report_type == "income-statement":
            # 本期发生额
            month_balances = await _get_account_balances(db, end_date, start_date, book_id=current_book.id)
            total_revenue = 0.0
            total_expenses = 0.0

            for acc in accounts:
                if acc.account_type not in ("revenue", "expense"):
                    continue
                bal = month_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
                if acc.balance_direction == "credit":
                    amount = bal["total_credit"] - bal["total_debit"]
                else:
                    amount = bal["total_debit"] - bal["total_credit"]

                if acc.account_type == "revenue":
                    total_revenue += amount
                else:
                    total_expenses += amount

            result_periods.append({
                "period": period,
                "total_revenue": round(total_revenue, 2),
                "total_expenses": round(total_expenses, 2),
                "net_profit": round(total_revenue - total_expenses, 2),
            })

    return mask_report_response({
        "report_type": report_type,
        "compare_type": compare_type,
        "periods": result_periods,
    }, current_user.role)


@router.get("/financial-ratios", summary="财务指标分析")
async def get_financial_ratios(
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    current_user: User = Depends(require_permission("report:view")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取财务指标分析数据"""
    start_date, end_date = _month_range(period)
    logger.info(f"用户 {current_user.username} 请求财务指标分析: {start_date} ~ {end_date}")

    accounts = await _get_all_accounts(db, current_book.id)
    # 期末余额（资产负债表）
    ending_balances = await _get_account_balances(db, end_date, book_id=current_book.id)
    # 本期发生额（利润表）
    month_balances = await _get_account_balances(db, end_date, start_date, book_id=current_book.id)

    def _get_balance(code_prefixes: tuple) -> float:
        """获取指定科目代码前缀的期末余额合计"""
        total = 0.0
        for acc in accounts:
            if not acc.account_code.startswith(code_prefixes):
                continue
            bal = ending_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
            if acc.balance_direction == "debit":
                total += bal["total_debit"] - bal["total_credit"]
            else:
                total += bal["total_credit"] - bal["total_debit"]
        return total

    def _get_month_amount(code_prefixes: tuple) -> float:
        """获取本期发生额"""
        total = 0.0
        for acc in accounts:
            if not acc.account_code.startswith(code_prefixes):
                continue
            bal = month_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
            if acc.balance_direction == "debit":
                total += bal["total_debit"] - bal["total_credit"]
            else:
                total += bal["total_credit"] - bal["total_debit"]
        return total

    # 流动资产 = 所有资产类科目（通常 1001-1499）
    current_assets = _get_balance(("1001", "1002", "1012", "1101", "1121", "1122", "1123", "1221", "1231", "1401", "1471"))
    # 存货 = 14xx (库存商品、原材料等)
    inventory = _get_balance(("1401", "1402", "1403", "1405", "1406", "1407", "1408", "1411", "1421", "1461", "1471"))
    # 流动负债 = 负债类科目 (2001-2249)
    current_liabilities = _get_balance(("2001", "2201", "2202", "2203", "2211", "2221", "2231", "2232", "2241"))
    # 资产总额
    total_assets = 0.0
    for acc in accounts:
        if acc.account_type != "asset":
            continue
        bal = ending_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        if acc.balance_direction == "debit":
            total_assets += bal["total_debit"] - bal["total_credit"]
        else:
            total_assets += bal["total_credit"] - bal["total_debit"]

    # 负债总额
    total_liabilities = 0.0
    for acc in accounts:
        if acc.account_type != "liability":
            continue
        bal = ending_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        if acc.balance_direction == "credit":
            total_liabilities += bal["total_credit"] - bal["total_debit"]
        else:
            total_liabilities += bal["total_debit"] - bal["total_credit"]

    # 所有者权益总额
    total_equity = 0.0
    for acc in accounts:
        if acc.account_type != "equity":
            continue
        bal = ending_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        if acc.balance_direction == "credit":
            total_equity += bal["total_credit"] - bal["total_debit"]
        else:
            total_equity += bal["total_debit"] - bal["total_credit"]

    # 收入
    total_revenue = 0.0
    for acc in accounts:
        if acc.account_type != "revenue":
            continue
        bal = month_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        if acc.balance_direction == "credit":
            total_revenue += bal["total_credit"] - bal["total_debit"]
        else:
            total_revenue += bal["total_debit"] - bal["total_credit"]

    # 成本费用
    total_cost = 0.0
    for acc in accounts:
        if acc.account_type not in ("expense", "cost"):
            continue
        bal = month_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        if acc.balance_direction == "debit":
            total_cost += bal["total_debit"] - bal["total_credit"]
        else:
            total_cost += bal["total_credit"] - bal["total_debit"]

    # 净利润
    net_profit = total_revenue - total_cost

    def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
        """安全计算比率，避免除零"""
        if denominator == 0:
            return None
        return round(numerator / denominator, 4)

    # 计算各项财务指标
    ratios = []
    reference_values = {
        "流动比率": {"min": 1.5, "max": 2.5, "unit": "倍"},
        "速动比率": {"min": 0.8, "max": 1.5, "unit": "倍"},
        "资产负债率": {"min": 0.3, "max": 0.6, "unit": "%"},
        "毛利率": {"min": 0.15, "max": 0.5, "unit": "%"},
        "净利率": {"min": 0.05, "max": 0.2, "unit": "%"},
        "ROE": {"min": 0.08, "max": 0.3, "unit": "%"},
        "ROA": {"min": 0.03, "max": 0.1, "unit": "%"},
    }

    def _ratio_status(name: str, value: Optional[float]) -> str:
        """判断指标状态"""
        if value is None:
            return "unknown"
        ref = reference_values.get(name, {})
        if not ref:
            return "normal"
        if value < ref["min"] * 0.7:
            return "danger"
        if value < ref["min"]:
            return "warning"
        if value > ref["max"] * 1.5:
            return "danger"
        if value > ref["max"]:
            return "warning"
        return "normal"

    # 流动比率
    current_ratio = _safe_ratio(current_assets, current_liabilities)
    ratios.append({
        "name": "流动比率",
        "value": current_ratio if current_ratio is not None else None,
        "formula": "流动资产 / 流动负债",
        "unit": "倍",
        "reference": "1.5 - 2.5",
        "status": _ratio_status("流动比率", current_ratio),
        "description": "衡量企业短期偿债能力",
    })

    # 速动比率
    quick_assets = current_assets - inventory
    quick_ratio = _safe_ratio(quick_assets, current_liabilities)
    ratios.append({
        "name": "速动比率",
        "value": quick_ratio if quick_ratio is not None else None,
        "formula": "(流动资产 - 存货) / 流动负债",
        "unit": "倍",
        "reference": "0.8 - 1.5",
        "status": _ratio_status("速动比率", quick_ratio),
        "description": "衡量企业立即偿债能力",
    })

    # 资产负债率
    debt_ratio = _safe_ratio(total_liabilities, total_assets)
    ratios.append({
        "name": "资产负债率",
        "value": debt_ratio * 100 if debt_ratio is not None else None,
        "formula": "负债总额 / 资产总额",
        "unit": "%",
        "reference": "30% - 60%",
        "status": _ratio_status("资产负债率", debt_ratio * 100 if debt_ratio is not None else None),
        "description": "衡量企业负债水平和风险程度",
    })

    # 毛利率
    gross_profit_margin = _safe_ratio(total_revenue - total_cost, total_revenue)
    ratios.append({
        "name": "毛利率",
        "value": gross_profit_margin * 100 if gross_profit_margin is not None else None,
        "formula": "(收入 - 成本) / 收入",
        "unit": "%",
        "reference": "15% - 50%",
        "status": _ratio_status("毛利率", gross_profit_margin * 100 if gross_profit_margin is not None else None),
        "description": "衡量企业销售盈利能力",
    })

    # 净利率
    net_margin = _safe_ratio(net_profit, total_revenue)
    ratios.append({
        "name": "净利率",
        "value": net_margin * 100 if net_margin is not None else None,
        "formula": "净利润 / 收入",
        "unit": "%",
        "reference": "5% - 20%",
        "status": _ratio_status("净利率", net_margin * 100 if net_margin is not None else None),
        "description": "衡量企业整体盈利能力",
    })

    # ROE (净资产收益率)
    roe = _safe_ratio(net_profit, total_equity)
    ratios.append({
        "name": "ROE（净资产收益率）",
        "value": roe * 100 if roe is not None else None,
        "formula": "净利润 / 所有者权益",
        "unit": "%",
        "reference": "8% - 30%",
        "status": _ratio_status("ROE", roe * 100 if roe is not None else None),
        "description": "衡量股东权益回报水平",
    })

    # ROA (总资产收益率)
    roa = _safe_ratio(net_profit, total_assets)
    ratios.append({
        "name": "ROA（总资产收益率）",
        "value": roa * 100 if roa is not None else None,
        "formula": "净利润 / 资产总额",
        "unit": "%",
        "reference": "3% - 10%",
        "status": _ratio_status("ROA", roa * 100 if roa is not None else None),
        "description": "衡量企业资产运用效率",
    })

    # 权益乘数
    equity_multiplier = _safe_ratio(total_assets, total_equity)
    ratios.append({
        "name": "权益乘数",
        "value": equity_multiplier if equity_multiplier is not None else None,
        "formula": "资产总额 / 所有者权益",
        "unit": "倍",
        "reference": "1.5 - 3.0",
        "status": "normal",
        "description": "衡量财务杠杆水平",
    })

    return mask_report_response({
        "period": end_date,
        "ratios": ratios,
        "summary": {
            "current_assets": round(current_assets, 2),
            "inventory": round(inventory, 2),
            "current_liabilities": round(current_liabilities, 2),
            "total_assets": round(total_assets, 2),
            "total_liabilities": round(total_liabilities, 2),
            "total_equity": round(total_equity, 2),
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "net_profit": round(net_profit, 2),
        },
    }, current_user.role)


@router.get("/export/{report_type}", summary="导出报表 Excel")
async def export_report(
    report_type: str,
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    current_user: User = Depends(require_permission("report:export")),
    db: AsyncSession = Depends(get_db),
):
    """导出报表为 Excel 文件"""
    valid_types = {"balance-sheet", "income-statement", "cash-flow", "account-ledger", "trial-balance", "trial-balance-summary"}
    if report_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的报表类型，有效类型: {', '.join(valid_types)}",
        )

    logger.info(f"用户 {current_user.username} 导出报表: {report_type}")

    # 获取报表数据
    if report_type == "balance-sheet":
        data = await get_balance_sheet(period=period, current_user=current_user, db=db)
    elif report_type == "income-statement":
        data = await get_income_statement(period=period, current_user=current_user, db=db)
    elif report_type == "cash-flow":
        data = await get_cash_flow(period=period, current_user=current_user, db=db)
    elif report_type == "account-ledger":
        data = await get_account_ledger(period=period, current_user=current_user, db=db)
    elif report_type == "trial-balance":
        data = await get_trial_balance(period=period, current_user=current_user, db=db)
    elif report_type == "trial-balance-summary":
        data = await get_trial_balance_summary(period=period, current_user=current_user, db=db)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的报表类型")

    # 简单 CSV 导出（后续可升级为真正的 Excel）
    import io
    import csv

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == "balance-sheet":
        writer.writerow(["科目代码", "科目名称", "期末余额"])
        for section in ["assets", "liabilities", "equity"]:
            section_name = {"assets": "资产", "liabilities": "负债", "equity": "所有者权益"}[section]
            writer.writerow([section_name, "", ""])
            for item in data[section]:
                writer.writerow([item["account_code"], item["account_name"], item["ending_balance"]])
        writer.writerow(["资产总计", "", data["total_assets"]])
        writer.writerow(["负债和所有者权益总计", "", data["total_liabilities_and_equity"]])
    elif report_type == "income-statement":
        writer.writerow(["科目代码", "科目名称", "本期金额", "本年累计金额"])
        writer.writerow(["收入", "", "", ""])
        for item in data["revenue"]:
            writer.writerow([item["account_code"], item["account_name"], item["current_amount"], item["cumulative_amount"]])
        writer.writerow(["收入合计", "", data["total_revenue"], ""])
        writer.writerow(["费用", "", "", ""])
        for item in data["expenses"]:
            writer.writerow([item["account_code"], item["account_name"], item["current_amount"], item["cumulative_amount"]])
        writer.writerow(["费用合计", "", data["total_expenses"], ""])
        writer.writerow(["净利润", "", data["net_profit"], ""])
    elif report_type in ("account-ledger", "trial-balance"):
        writer.writerow(["科目代码", "科目名称", "期初借方", "期初贷方", "本期借方", "本期贷方", "期末借方", "期末贷方"])
        for item in data["items"]:
            writer.writerow([item["account_code"], item["account_name"],
                             item["beginning_debit"], item["beginning_credit"],
                             item["current_debit"], item["current_credit"],
                             item["ending_debit"], item["ending_credit"]])
    elif report_type == "trial-balance-summary":
        writer.writerow(["科目代码", "科目名称", "科目类型", "余额方向", "期初借方", "期初贷方", "本期借方", "本期贷方", "期末借方", "期末贷方"])
        for item in data["items"]:
            writer.writerow([item["account_code"], item["account_name"],
                             item["account_type"], item["balance_direction"],
                             item["beginning_debit"], item["beginning_credit"],
                             item["current_debit"], item["current_credit"],
                             item["ending_debit"], item["ending_credit"]])
        summary = data.get("summary", {})
        check = data.get("balance_check", {})
        writer.writerow([])
        writer.writerow(["汇总", "", "", "", "", "", "", "", "", ""])
        writer.writerow(["期初借方合计", summary.get("total_beginning_debit", 0)])
        writer.writerow(["期初贷方合计", summary.get("total_beginning_credit", 0)])
        writer.writerow(["本期借方合计", summary.get("total_current_debit", 0)])
        writer.writerow(["本期贷方合计", summary.get("total_current_credit", 0)])
        writer.writerow(["期末借方合计", summary.get("total_ending_debit", 0)])
        writer.writerow(["期末贷方合计", summary.get("total_ending_credit", 0)])
        writer.writerow(["试算平衡", "平衡" if check.get("is_balanced") else "不平衡"])
    else:
        # 现金流量表导出
        writer.writerow(["类别", "方向", "凭证号", "凭证日期", "科目代码", "科目名称", "摘要", "金额"])
        for category in ["operating", "investing", "financing"]:
            cat_data = data.get(category, {})
            cat_name = {"operating": "经营活动", "investing": "投资活动", "financing": "筹资活动"}[category]
            for item in cat_data.get("inflow", []):
                writer.writerow([cat_name, "流入", item.get("voucher_no", ""), item.get("voucher_date", ""),
                                 item.get("account_code", ""), item.get("account_name", ""),
                                 item.get("summary", ""), item.get("amount", 0)])
            for item in cat_data.get("outflow", []):
                writer.writerow([cat_name, "流出", item.get("voucher_no", ""), item.get("voucher_date", ""),
                                 item.get("account_code", ""), item.get("account_name", ""),
                                 item.get("summary", ""), -item.get("amount", 0)])
            writer.writerow([cat_name + "净额", "", "", "", "", "", "", cat_data.get("net", 0)])
        writer.writerow(["现金净增加额", "", "", "", "", "", "", data.get("net_cash_flow", 0)])

    csv_content = output.getvalue()
    output.close()

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={report_type}_{period or 'report'}.csv"
        },
    )