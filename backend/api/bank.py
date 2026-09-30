"""
银行对账 API
"""
import csv
import io
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

from database import get_db
from models.user import User
from models.bank_statement import BankStatement
from models.voucher import Voucher, VoucherItem, Account
from auth.middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bank", tags=["银行对账"])


# ========== 请求/响应模型 ==========

class BankStatementResponse(BaseModel):
    id: int
    transaction_date: str
    description: str
    debit_amount: float
    credit_amount: float
    balance: float
    match_status: str
    matched_voucher_id: Optional[int] = None
    matched_voucher_item_id: Optional[int] = None
    notes: Optional[str] = None


class MatchResult(BaseModel):
    statement_id: int
    matched: bool
    voucher_id: Optional[int] = None
    voucher_no: Optional[str] = None
    reason: str = ""


class ReconciliationReport(BaseModel):
    bank_balance: float
    book_balance: float
    matched_count: int
    unmatched_bank_count: int
    unmatched_book_count: int
    difference: float


class ManualMatchRequest(BaseModel):
    voucher_item_id: int = Field(..., description="凭证分录ID")


class ManualStatementRequest(BaseModel):
    bank_account: str = Field(..., description="银行账号")
    transaction_date: str = Field(..., description="交易日期(YYYY-MM-DD)")
    description: str = Field(..., description="交易摘要")
    debit_amount: float = Field(default=0, description="借方金额")
    credit_amount: float = Field(default=0, description="贷方金额")
    balance: float = Field(default=0, description="余额")
    notes: Optional[str] = Field(default=None, description="备注")


class VoucherItemInfo(BaseModel):
    id: int
    voucher_id: int
    voucher_no: str
    voucher_date: str
    account_code: str
    account_name: str
    description: str
    debit_amount: float
    credit_amount: float


# ========== API 端点 ==========

@router.get("/statements", summary="获取银行对账单列表")
async def list_statements(
    bank_account: Optional[str] = Query(None, description="银行账号"),
    match_status: Optional[str] = Query(None, description="匹配状态"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取银行对账单列表"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    conditions = [BankStatement.book_id == book_id]
    if bank_account:
        conditions.append(BankStatement.bank_account == bank_account)
    if match_status:
        conditions.append(BankStatement.match_status == match_status)
    if start_date:
        conditions.append(BankStatement.transaction_date >= date.fromisoformat(start_date))
    if end_date:
        conditions.append(BankStatement.transaction_date <= date.fromisoformat(end_date))

    # 总数
    count_query = select(func.count()).select_from(BankStatement).where(and_(*conditions))
    total = (await db.execute(count_query)).scalar()

    # 分页查询
    query = (
        select(BankStatement)
        .where(and_(*conditions))
        .order_by(BankStatement.transaction_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    statements = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            BankStatementResponse(
                id=s.id,
                transaction_date=s.transaction_date.isoformat(),
                description=s.description,
                debit_amount=s.debit_amount,
                credit_amount=s.credit_amount,
                balance=s.balance,
                match_status=s.match_status,
                matched_voucher_id=s.matched_voucher_id,
                matched_voucher_item_id=s.matched_voucher_item_id,
                notes=s.notes,
            )
            for s in statements
        ],
    }


@router.post("/statements/import", summary="导入银行对账单")
async def import_statements(
    file: UploadFile = File(...),
    bank_account: str = Query(..., description="银行账号"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从CSV文件导入银行对账单"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="仅支持CSV格式")

    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        try:
            text = content.decode('gbk')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="无法解析文件编码，请使用UTF-8或GBK编码")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=400, detail="无法解析CSV表头")

    imported = 0
    skipped = 0
    for row in reader:
        try:
            trans_date = date.fromisoformat(row.get('日期', row.get('date', '')))
            desc = row.get('摘要', row.get('description', ''))
            debit = float(row.get('借方金额', row.get('debit', 0)) or 0)
            credit = float(row.get('贷方金额', row.get('credit', 0)) or 0)
            balance = float(row.get('余额', row.get('balance', 0)) or 0)

            if not desc:
                skipped += 1
                continue

            db.add(BankStatement(
                book_id=book_id,
                bank_account=bank_account,
                transaction_date=trans_date,
                description=desc,
                debit_amount=debit,
                credit_amount=credit,
                balance=balance,
                match_status="unmatched",
            ))
            imported += 1
        except (ValueError, KeyError):
            skipped += 1

    await db.commit()
    return {
        "message": f"导入完成: 成功 {imported} 条, 跳过 {skipped} 条",
        "imported": imported,
        "skipped": skipped,
    }


@router.post("/statements/auto-match", summary="自动匹配银行流水")
async def auto_match_statements(
    bank_account: str = Query(..., description="银行账号"),
    date_tolerance: int = Query(3, description="日期容差(天)"),
    amount_tolerance: float = Query(0.01, description="金额容差"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自动匹配银行流水与凭证分录"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    # 获取未匹配的银行流水
    stmt_result = await db.execute(
        select(BankStatement).where(
            BankStatement.book_id == book_id,
            BankStatement.bank_account == bank_account,
            BankStatement.match_status == "unmatched",
        )
    )
    unmatched_statements = stmt_result.scalars().all()

    # 获取银行科目下的所有已审核凭证分录
    bank_accounts = await db.execute(
        select(Account).where(
            Account.book_id == book_id,
            Account.account_code.in_(["1002", "1012"]),
        )
    )
    bank_codes = [a.account_code for a in bank_accounts.scalars().all()]
    if not bank_codes:
        bank_codes = ["1002", "1012"]

    item_result = await db.execute(
        select(VoucherItem, Voucher.voucher_no, Voucher.voucher_date)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            VoucherItem.account_code.in_(bank_codes),
            Voucher.book_id == book_id,
            Voucher.status.in_(["reviewed", "posted"]),
        )
    )
    voucher_items = item_result.all()

    results = []
    for stmt in unmatched_statements:
        matched = False
        stmt_amount = stmt.debit_amount if stmt.debit_amount > 0 else -stmt.credit_amount

        for item, voucher_no, voucher_date in voucher_items:
            item_amount = float(item.debit_amount) - float(item.credit_amount)
            date_diff = abs((stmt.transaction_date - voucher_date).days)

            if date_diff <= date_tolerance and abs(stmt_amount - item_amount) <= amount_tolerance:
                stmt.matched_voucher_id = item.voucher_id
                stmt.matched_voucher_item_id = item.id
                stmt.match_status = "matched"
                stmt.match_confidence = max(0, 100 - date_diff * 10)
                matched = True
                results.append(MatchResult(
                    statement_id=stmt.id,
                    matched=True,
                    voucher_id=item.voucher_id,
                    voucher_no=voucher_no,
                    reason=f"金额匹配({stmt_amount} = {item_amount}), 日期差{date_diff}天",
                ))
                break

        if not matched:
            results.append(MatchResult(
                statement_id=stmt.id,
                matched=False,
                reason="未找到匹配的凭证分录",
            ))

    await db.commit()
    matched_count = sum(1 for r in results if r.matched)
    return {
        "message": f"自动匹配完成: {matched_count}/{len(results)} 条匹配成功",
        "matched_count": matched_count,
        "total": len(results),
        "details": [r.model_dump() for r in results],
    }


@router.delete("/statements/{statement_id}", summary="删除对账单记录")
async def delete_statement(
    statement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除单条对账单记录"""
    book_id = current_user.current_book_id
    result = await db.execute(
        select(BankStatement).where(
            BankStatement.id == statement_id,
            BankStatement.book_id == book_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="记录不存在")

    await db.delete(stmt)
    await db.commit()
    return {"message": "删除成功"}


@router.delete("/statements", summary="清空对账单")
async def clear_statements(
    bank_account: str = Query(..., description="银行账号"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空指定银行账号的对账单"""
    book_id = current_user.current_book_id
    await db.execute(
        BankStatement.__table__.delete().where(
            BankStatement.book_id == book_id,
            BankStatement.bank_account == bank_account,
        )
    )
    await db.commit()
    return {"message": "清空成功"}


@router.get("/reconciliation", summary="获取对账报告")
async def get_reconciliation_report(
    bank_account: str = Query(..., description="银行账号"),
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成银行对账报告"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    s_date = date.fromisoformat(start_date)
    e_date = date.fromisoformat(end_date)

    # 银行余额
    bank_result = await db.execute(
        select(
            func.coalesce(func.sum(BankStatement.debit_amount), 0),
            func.coalesce(func.sum(BankStatement.credit_amount), 0),
        ).where(
            BankStatement.book_id == book_id,
            BankStatement.bank_account == bank_account,
            BankStatement.transaction_date.between(s_date, e_date),
        )
    )
    bank_debit, bank_credit = bank_result.one()
    bank_balance = float(bank_debit) - float(bank_credit)

    # 日记账余额
    bank_accounts = await db.execute(
        select(Account).where(
            Account.book_id == book_id,
            Account.account_code.in_(["1002", "1012"]),
        )
    )
    bank_codes = [a.account_code for a in bank_accounts.scalars().all()]
    if not bank_codes:
        bank_codes = ["1002", "1012"]

    book_result = await db.execute(
        select(
            func.coalesce(func.sum(VoucherItem.debit_amount), 0),
            func.coalesce(func.sum(VoucherItem.credit_amount), 0),
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            VoucherItem.account_code.in_(bank_codes),
            Voucher.book_id == book_id,
            Voucher.status.in_(["reviewed", "posted"]),
            Voucher.voucher_date.between(s_date, e_date),
        )
    )
    book_debit, book_credit = book_result.one()
    book_balance = float(book_debit) - float(book_credit)

    # 匹配统计
    match_result = await db.execute(
        select(
            func.count(),
            func.sum(
                func.case((BankStatement.match_status == "matched", 1), else_=0)
            ),
            func.sum(
                func.case((BankStatement.match_status == "unmatched", 1), else_=0)
            ),
        ).where(
            BankStatement.book_id == book_id,
            BankStatement.bank_account == bank_account,
            BankStatement.transaction_date.between(s_date, e_date),
        )
    )
    total, matched, unmatched = match_result.one()

    return ReconciliationReport(
        bank_balance=bank_balance,
        book_balance=book_balance,
        matched_count=int(matched or 0),
        unmatched_bank_count=int(unmatched or 0),
        unmatched_book_count=0,  # 需要单独计算未匹配的凭证分录
        difference=round(bank_balance - book_balance, 2),
    ).model_dump()


@router.post("/statements/{statement_id}/match", summary="手动匹配银行流水")
async def manual_match(
    statement_id: int,
    req: ManualMatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动将银行流水与凭证分录匹配"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    result = await db.execute(
        select(BankStatement).where(
            BankStatement.id == statement_id,
            BankStatement.book_id == book_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="银行流水记录不存在")
    if stmt.match_status == "matched":
        raise HTTPException(status_code=400, detail="该流水已匹配，请先取消匹配")

    item_result = await db.execute(
        select(VoucherItem, Voucher.voucher_no, Voucher.voucher_date)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            VoucherItem.id == req.voucher_item_id,
            Voucher.book_id == book_id,
        )
    )
    row = item_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="凭证分录不存在")

    item, voucher_no, voucher_date = row
    stmt.matched_voucher_id = item.voucher_id
    stmt.matched_voucher_item_id = item.id
    stmt.match_status = "matched"
    stmt.match_confidence = 100
    await db.commit()

    return {
        "message": "匹配成功",
        "statement_id": statement_id,
        "voucher_no": voucher_no,
    }


@router.post("/statements/{statement_id}/unmatch", summary="取消匹配银行流水")
async def unmatch_statement(
    statement_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """取消银行流水的匹配状态"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    result = await db.execute(
        select(BankStatement).where(
            BankStatement.id == statement_id,
            BankStatement.book_id == book_id,
        )
    )
    stmt = result.scalar_one_or_none()
    if not stmt:
        raise HTTPException(status_code=404, detail="银行流水记录不存在")
    if stmt.match_status != "matched":
        raise HTTPException(status_code=400, detail="该流水未匹配，无需取消")

    stmt.matched_voucher_id = None
    stmt.matched_voucher_item_id = None
    stmt.match_status = "unmatched"
    stmt.match_confidence = 0
    await db.commit()

    return {"message": "已取消匹配", "statement_id": statement_id}


@router.post("/statements/manual", summary="手动添加银行流水")
async def add_statement_manual(
    req: ManualStatementRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动添加一条银行流水记录"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    try:
        trans_date = date.fromisoformat(req.transaction_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式不正确，应为YYYY-MM-DD")

    new_stmt = BankStatement(
        book_id=book_id,
        bank_account=req.bank_account,
        transaction_date=trans_date,
        description=req.description,
        debit_amount=req.debit_amount,
        credit_amount=req.credit_amount,
        balance=req.balance,
        match_status="unmatched",
        notes=req.notes,
    )
    db.add(new_stmt)
    await db.commit()
    await db.refresh(new_stmt)

    return {
        "message": "添加成功",
        "id": new_stmt.id,
    }


@router.get("/voucher-items", summary="查询可匹配的凭证分录")
async def list_voucher_items(
    bank_account: Optional[str] = Query(None, description="银行账号"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询银行科目下可匹配的凭证分录"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    bank_accounts = await db.execute(
        select(Account).where(
            Account.book_id == book_id,
            Account.account_code.in_(["1001", "1002", "1012"]),
        )
    )
    bank_codes = [a.account_code for a in bank_accounts.scalars().all()]
    if not bank_codes:
        bank_codes = ["1001", "1002", "1012"]

    conditions = [
        VoucherItem.account_code.in_(bank_codes),
        Voucher.book_id == book_id,
        Voucher.status.in_(["reviewed", "posted"]),
    ]
    if keyword:
        conditions.append(
            (VoucherItem.description.ilike(f"%{keyword}%"))
            | (Voucher.voucher_no.ilike(f"%{keyword}%"))
        )

    query = (
        select(VoucherItem, Voucher.voucher_no, Voucher.voucher_date)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(and_(*conditions))
        .order_by(Voucher.voucher_date.desc())
        .limit(200)
    )
    result = await db.execute(query)
    rows = result.all()

    return {
        "items": [
            VoucherItemInfo(
                id=item.id,
                voucher_id=item.voucher_id,
                voucher_no=voucher_no,
                voucher_date=voucher_date.isoformat(),
                account_code=item.account_code,
                account_name=item.account_name,
                description=item.description,
                debit_amount=float(item.debit_amount),
                credit_amount=float(item.credit_amount),
            )
            for item, voucher_no, voucher_date in rows
        ],
    }


@router.get("/reconciliation/export", summary="导出对账结果")
async def export_reconciliation(
    bank_account: str = Query(..., description="银行账号"),
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """导出对账结果为Excel文件"""
    book_id = current_user.current_book_id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    s_date = date.fromisoformat(start_date)
    e_date = date.fromisoformat(end_date)

    wb = Workbook()
    header_font = Font(bold=True, size=11)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_font_white = Font(bold=True, size=11, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    center_align = Alignment(horizontal="center", vertical="center")
    money_format = '#,##0.00'

    # ---- Sheet 1: 对账汇总 ----
    ws1 = wb.active
    ws1.title = "对账汇总"

    # 银行余额
    bank_result = await db.execute(
        select(
            func.coalesce(func.sum(BankStatement.debit_amount), 0),
            func.coalesce(func.sum(BankStatement.credit_amount), 0),
        ).where(
            BankStatement.book_id == book_id,
            BankStatement.bank_account == bank_account,
            BankStatement.transaction_date.between(s_date, e_date),
        )
    )
    bank_debit, bank_credit = bank_result.one()
    bank_balance = float(bank_debit) - float(bank_credit)

    # 日记账余额
    bank_accounts = await db.execute(
        select(Account).where(
            Account.book_id == book_id,
            Account.account_code.in_(["1001", "1002", "1012"]),
        )
    )
    bank_codes = [a.account_code for a in bank_accounts.scalars().all()]
    if not bank_codes:
        bank_codes = ["1001", "1002", "1012"]

    book_result = await db.execute(
        select(
            func.coalesce(func.sum(VoucherItem.debit_amount), 0),
            func.coalesce(func.sum(VoucherItem.credit_amount), 0),
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            VoucherItem.account_code.in_(bank_codes),
            Voucher.book_id == book_id,
            Voucher.status.in_(["reviewed", "posted"]),
            Voucher.voucher_date.between(s_date, e_date),
        )
    )
    book_debit, book_credit = book_result.one()
    book_balance = float(book_debit) - float(book_credit)

    # 匹配统计
    match_result = await db.execute(
        select(
            func.count(),
            func.sum(func.case((BankStatement.match_status == "matched", 1), else_=0)),
            func.sum(func.case((BankStatement.match_status == "unmatched", 1), else_=0)),
        ).where(
            BankStatement.book_id == book_id,
            BankStatement.bank_account == bank_account,
            BankStatement.transaction_date.between(s_date, e_date),
        )
    )
    total, matched, unmatched = match_result.one()

    ws1.merge_cells("A1:E1")
    ws1["A1"] = "银行对账报告"
    ws1["A1"].font = Font(bold=True, size=16)
    ws1["A1"].alignment = center_align

    ws1.merge_cells("A2:E2")
    ws1["A2"] = f"银行账号: {bank_account}  期间: {start_date} 至 {end_date}"
    ws1["A2"].font = Font(size=11)

    summary_data = [
        ["项目", "金额", "", "", ""],
        ["银行余额", bank_balance, "", "", ""],
        ["账面余额", book_balance, "", "", ""],
        ["差异", round(bank_balance - book_balance, 2), "", "", ""],
        ["", "", "", "", ""],
        ["已匹配笔数", int(matched or 0), "", "", ""],
        ["未匹配笔数", int(unmatched or 0), "", "", ""],
    ]
    for i, row_data in enumerate(summary_data, start=4):
        for j, val in enumerate(row_data, start=1):
            cell = ws1.cell(row=i, column=j, value=val)
            if i == 4:
                cell.font = header_font_white
                cell.fill = header_fill
                cell.border = thin_border
                cell.alignment = center_align
            elif j == 2 and isinstance(val, (int, float)):
                cell.number_format = money_format
                cell.border = thin_border
            else:
                cell.border = thin_border

    ws1.column_dimensions["A"].width = 18
    ws1.column_dimensions["B"].width = 20

    # ---- Sheet 2: 已匹配明细 ----
    ws2 = wb.create_sheet("已匹配明细")
    matched_headers = ["交易日期", "摘要", "借方金额", "贷方金额", "余额", "匹配凭证号"]
    for j, h in enumerate(matched_headers, start=1):
        cell = ws2.cell(row=1, column=j, value=h)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = center_align

    matched_stmts = await db.execute(
        select(BankStatement).where(
            BankStatement.book_id == book_id,
            BankStatement.bank_account == bank_account,
            BankStatement.match_status == "matched",
            BankStatement.transaction_date.between(s_date, e_date),
        ).order_by(BankStatement.transaction_date.desc())
    )
    for i, s in enumerate(matched_stmts.scalars().all(), start=2):
        ws2.cell(row=i, column=1, value=s.transaction_date.isoformat()).border = thin_border
        ws2.cell(row=i, column=2, value=s.description).border = thin_border
        ws2.cell(row=i, column=3, value=s.debit_amount).number_format = money_format
        ws2.cell(row=i, column=3).border = thin_border
        ws2.cell(row=i, column=4, value=s.credit_amount).number_format = money_format
        ws2.cell(row=i, column=4).border = thin_border
        ws2.cell(row=i, column=5, value=s.balance).number_format = money_format
        ws2.cell(row=i, column=5).border = thin_border
        ws2.cell(row=i, column=6, value=f"凭证#{s.matched_voucher_id}" if s.matched_voucher_id else "").border = thin_border

    ws2.column_dimensions["A"].width = 14
    ws2.column_dimensions["B"].width = 40
    ws2.column_dimensions["C"].width = 16
    ws2.column_dimensions["D"].width = 16
    ws2.column_dimensions["E"].width = 16
    ws2.column_dimensions["F"].width = 16

    # ---- Sheet 3: 未匹配明细（银行已记企业未记） ----
    ws3 = wb.create_sheet("未达账项-银行已记企业未记")
    unmatched_headers = ["交易日期", "摘要", "借方金额", "贷方金额", "余额", "备注"]
    for j, h in enumerate(unmatched_headers, start=1):
        cell = ws3.cell(row=1, column=j, value=h)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = center_align

    unmatched_stmts = await db.execute(
        select(BankStatement).where(
            BankStatement.book_id == book_id,
            BankStatement.bank_account == bank_account,
            BankStatement.match_status == "unmatched",
            BankStatement.transaction_date.between(s_date, e_date),
        ).order_by(BankStatement.transaction_date.desc())
    )
    for i, s in enumerate(unmatched_stmts.scalars().all(), start=2):
        ws3.cell(row=i, column=1, value=s.transaction_date.isoformat()).border = thin_border
        ws3.cell(row=i, column=2, value=s.description).border = thin_border
        ws3.cell(row=i, column=3, value=s.debit_amount).number_format = money_format
        ws3.cell(row=i, column=3).border = thin_border
        ws3.cell(row=i, column=4, value=s.credit_amount).number_format = money_format
        ws3.cell(row=i, column=4).border = thin_border
        ws3.cell(row=i, column=5, value=s.balance).number_format = money_format
        ws3.cell(row=i, column=5).border = thin_border
        ws3.cell(row=i, column=6, value=s.notes or "").border = thin_border

    ws3.column_dimensions["A"].width = 14
    ws3.column_dimensions["B"].width = 40
    ws3.column_dimensions["C"].width = 16
    ws3.column_dimensions["D"].width = 16
    ws3.column_dimensions["E"].width = 16
    ws3.column_dimensions["F"].width = 20

    # ---- Sheet 4: 余额调节表 ----
    ws4 = wb.create_sheet("余额调节表")
    ws4.merge_cells("A1:D1")
    ws4["A1"] = "银行存款余额调节表"
    ws4["A1"].font = Font(bold=True, size=14)
    ws4["A1"].alignment = center_align

    ws4.merge_cells("A2:D2")
    ws4["A2"] = f"账号: {bank_account}  日期: {end_date}"
    ws4["A2"].font = Font(size=11)

    adj_headers = ["项目", "金额", "项目", "金额"]
    for j, h in enumerate(adj_headers, start=1):
        cell = ws4.cell(row=4, column=j, value=h)
        cell.font = header_font_white
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = center_align

    adj_data = [
        ["银行对账单余额", bank_balance, "企业账面余额", book_balance],
        ["加: 企业已收银行未收", "", "加: 银行已收企业未收", ""],
        ["减: 企业已付银行未付", "", "减: 银行已付企业未付", ""],
        ["调节后余额", bank_balance, "调节后余额", book_balance],
    ]
    for i, row_data in enumerate(adj_data, start=5):
        for j, val in enumerate(row_data, start=1):
            cell = ws4.cell(row=i, column=j, value=val)
            if isinstance(val, (int, float)):
                cell.number_format = money_format
            cell.border = thin_border
            if i == 5 or i == 8:
                cell.font = Font(bold=True)

    ws4.column_dimensions["A"].width = 28
    ws4.column_dimensions["B"].width = 18
    ws4.column_dimensions["C"].width = 28
    ws4.column_dimensions["D"].width = 18

    # 写入内存
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"银行对账_{bank_account}_{start_date}_{end_date}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )