"""
数据导入导出 API 路由
提供 Excel 导入凭证/科目、Excel 导出报表、数据库备份与恢复功能
"""
import io
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db, async_session_maker
from models.user import User
from models.voucher import Voucher, VoucherItem, Account
from auth.middleware import get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["数据导入导出"])


# ========== 辅助函数 ==========

def _generate_voucher_no() -> str:
    """生成凭证号"""
    now = datetime.now()
    return f"PZ-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}{now.microsecond // 1000:03d}"


def _read_excel_rows(file_content: bytes) -> list[dict]:
    """读取 Excel 文件内容，返回字典列表"""
    from openpyxl import load_workbook
    wb = load_workbook(filename=io.BytesIO(file_content), read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Excel 文件没有活动工作表")

    rows = list(ws.iter_rows(min_row=1, values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Excel 文件至少需要包含表头行和一行数据")

    headers = [str(h).strip() if h else "" for h in rows[0]]
    result = []
    for row in rows[1:]:
        if row is None or all(c is None or str(c).strip() == "" for c in row):
            continue
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(row):
                val = row[i]
                row_dict[header] = str(val).strip() if val is not None else ""
            else:
                row_dict[header] = ""
        result.append(row_dict)
    wb.close()
    return result


def _safe_float(value) -> float:
    """安全地将值转换为 float"""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _safe_date(value) -> Optional[date]:
    """安全地将值转换为 date"""
    import re
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%m/%d/%Y", "%d/%m/%Y"]:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # 尝试从 Excel 数字格式解析
    match = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return None


def _style_header_cell(ws, row, col, value, width=None):
    """设置表头单元格样式"""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="微软雅黑", bold=True, size=11, color="FFFFFF")
    cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    cell.border = thin_border
    if width:
        ws.column_dimensions[ws.cell(row=row, column=col).column_letter].width = width


def _style_data_cell(ws, row, col, value, fmt=None, is_number=False):
    """设置数据单元格样式"""
    from openpyxl.styles import Font, Alignment, Border, Side, numbers
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(name="微软雅黑", size=10)
    if is_number:
        cell.alignment = Alignment(horizontal="right", vertical="center")
        if fmt:
            cell.number_format = fmt
    else:
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    cell.border = thin_border


def _build_excel_response(wb, filename: str) -> Response:
    """将 workbook 写入字节流并返回 Response"""
    output = io.BytesIO()
    wb.save(output)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _month_range(period: str) -> tuple:
    """根据月份字符串计算起止日期"""
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


async def _get_account_balances(db: AsyncSession, end_date: str, start_date: Optional[str] = None) -> dict:
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
    if start_date:
        query = query.where(Voucher.voucher_date >= start_date)
    result = await db.execute(query)
    rows = result.all()
    balances = {}
    for row in rows:
        code = row.account_code
        balances[code] = {
            "account_name": row.account_name,
            "total_debit": float(row.total_debit or 0),
            "total_credit": float(row.total_credit or 0),
        }
    return balances


async def _get_all_accounts(db: AsyncSession) -> list:
    """获取所有活跃科目"""
    result = await db.execute(
        select(Account).where(Account.is_active == True).order_by(Account.account_code)
    )
    return result.scalars().all()


# ========== 导入响应模型 ==========

class ImportResult(BaseModel):
    """导入结果"""
    success_count: int = 0
    error_count: int = 0
    total_count: int = 0
    errors: List[dict] = []


# ========== 模板下载端点 ==========

@router.get("/templates/voucher-import", summary="下载凭证导入模板")
async def download_voucher_template(current_user: User = Depends(get_current_user)):
    """下载凭证批量导入的 Excel 模板"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "凭证导入模板"

    headers = ["voucher_date", "summary", "account_code", "account_name", "description", "debit_amount", "credit_amount"]
    widths = [18, 30, 15, 20, 30, 15, 15]

    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        _style_header_cell(ws, 1, i, h, w)

    # 示例数据行
    sample = ["2026-01-15", "购买办公用品", "1001", "银行存款", "支付办公用品费", "0", "5000.00"]
    sample2 = ["2026-01-15", "购买办公用品", "6602", "管理费用", "办公费用支出", "5000.00", "0"]
    for j, (row_data, row_num) in enumerate([(sample, 2), (sample2, 3)], start=0):
        for i, val in enumerate(row_data, start=1):
            _style_data_cell(ws, row_num, i, val)

    ws.freeze_panes = "A2"
    return _build_excel_response(wb, "voucher_import_template.xlsx")


@router.get("/templates/account-import", summary="下载科目导入模板")
async def download_account_template(current_user: User = Depends(get_current_user)):
    """下载科目批量导入的 Excel 模板"""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "科目导入模板"

    headers = ["account_code", "account_name", "account_type", "parent_code", "balance_direction"]
    widths = [15, 20, 15, 15, 18]

    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        _style_header_cell(ws, 1, i, h, w)

    sample = ["1001", "库存现金", "asset", "", "debit"]
    sample2 = ["1002", "银行存款", "asset", "", "debit"]
    for j, (row_data, row_num) in enumerate([(sample, 2), (sample2, 3)], start=0):
        for i, val in enumerate(row_data, start=1):
            _style_data_cell(ws, row_num, i, val)

    ws.freeze_panes = "A2"
    return _build_excel_response(wb, "account_import_template.xlsx")


# ========== 凭证导入预览 ==========

class PreviewItem(BaseModel):
    """导入预览条目"""
    row: int
    voucher_date: str = ""
    summary: str = ""
    account_code: str = ""
    account_name: str = ""
    description: str = ""
    debit_amount: float = 0.0
    credit_amount: float = 0.0
    voucher_group: int = 0


class PreviewResult(BaseModel):
    """导入预览结果"""
    items: List[dict] = []
    total_rows: int = 0
    voucher_count: int = 0
    errors: List[dict] = []


@router.post("/import/vouchers/preview", response_model=PreviewResult, summary="预览凭证导入数据")
async def preview_voucher_import(
    file: UploadFile = File(..., description="Excel 文件 (.xlsx)"),
    current_user: User = Depends(require_permission("voucher:create")),
):
    """预览 Excel 凭证导入数据，不实际导入"""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传 .xlsx 格式的 Excel 文件")

    content = await file.read()
    try:
        rows = _read_excel_rows(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Excel 解析失败: {str(e)}")

    result = PreviewResult(total_rows=len(rows))
    errors = []
    preview_items = []

    # 按 voucher_date + summary 分组
    groups: dict[str, list] = {}
    for idx, row in enumerate(rows, start=2):
        vd = row.get("voucher_date", "")
        summary = row.get("summary", "")
        if not vd or not summary:
            errors.append({"row": idx, "message": "凭证日期和摘要不能为空"})
            continue
        key = f"{vd}|||{summary}"
        if key not in groups:
            groups[key] = []
        groups[key].append({"row": idx, "data": row})

    group_idx = 0
    for key, items in groups.items():
        group_idx += 1
        vd_str, summary = key.split("|||", 1)
        voucher_date = _safe_date(vd_str)
        if voucher_date is None:
            for item in items:
                errors.append({"row": item["row"], "message": f"无效的日期格式: {vd_str}"})
            continue

        total_debit = 0.0
        total_credit = 0.0
        valid_items = []
        for item in items:
            debit = _safe_float(item["data"].get("debit_amount", 0))
            credit = _safe_float(item["data"].get("credit_amount", 0))
            account_code = item["data"].get("account_code", "")
            account_name = item["data"].get("account_name", "")
            description = item["data"].get("description", "")
            if not account_code or not account_name:
                errors.append({"row": item["row"], "message": "科目编码和科目名称不能为空"})
                continue
            valid_items.append({
                "row": item["row"],
                "voucher_date": str(voucher_date),
                "summary": summary,
                "account_code": account_code,
                "account_name": account_name,
                "description": description,
                "debit_amount": round(debit, 2),
                "credit_amount": round(credit, 2),
                "voucher_group": group_idx,
            })
            total_debit += debit
            total_credit += credit

        if not valid_items:
            continue

        if abs(total_debit - total_credit) > 0.01:
            for vi in valid_items:
                vi["_warning"] = f"借贷不平衡: 借方={round(total_debit, 2)}, 贷方={round(total_credit, 2)}"

        preview_items.extend(valid_items)

    result.items = preview_items
    result.voucher_count = group_idx
    result.errors = errors
    return result


# ========== 凭证导入 ==========

@router.post("/import/vouchers", response_model=ImportResult, summary="批量导入凭证")
async def import_vouchers(
    file: UploadFile = File(..., description="Excel 文件 (.xlsx)"),
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """从 Excel 文件批量导入凭证"""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传 .xlsx 格式的 Excel 文件")

    content = await file.read()
    try:
        rows = _read_excel_rows(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Excel 解析失败: {str(e)}")

    result = ImportResult(total_count=len(rows))
    errors = []

    # 按 voucher_date + summary 分组
    groups: dict[str, list] = {}
    for idx, row in enumerate(rows, start=2):
        vd = row.get("voucher_date", "")
        summary = row.get("summary", "")
        if not vd or not summary:
            errors.append({"row": idx, "message": "凭证日期和摘要不能为空"})
            continue
        key = f"{vd}|||{summary}"
        if key not in groups:
            groups[key] = []
        groups[key].append({"row": idx, "data": row})

    if errors:
        result.error_count = len(errors)
        result.errors = errors
        return result

    for key, items in groups.items():
        vd_str, summary = key.split("|||", 1)
        voucher_date = _safe_date(vd_str)
        if voucher_date is None:
            for item in items:
                errors.append({"row": item["row"], "message": f"无效的日期格式: {vd_str}"})
            continue

        # 检查借贷平衡
        total_debit = 0.0
        total_credit = 0.0
        valid_items = []
        for item in items:
            debit = _safe_float(item["data"].get("debit_amount", 0))
            credit = _safe_float(item["data"].get("credit_amount", 0))
            account_code = item["data"].get("account_code", "")
            account_name = item["data"].get("account_name", "")
            description = item["data"].get("description", "")
            if not account_code or not account_name:
                errors.append({"row": item["row"], "message": "科目编码和科目名称不能为空"})
                continue
            valid_items.append((item["row"], account_code, account_name, description, debit, credit))
            total_debit += debit
            total_credit += credit

        if not valid_items:
            continue

        if abs(total_debit - total_credit) > 0.01:
            for item in items:
                errors.append({"row": item["row"], "message": f"凭证借贷不平衡: 借方={total_debit}, 贷方={total_credit}"})
            continue

        # 创建凭证
        try:
            voucher = Voucher(
                voucher_no=_generate_voucher_no(),
                voucher_date=voucher_date,
                summary=summary,
                status="draft",
                created_by=current_user.id,
            )
            db.add(voucher)
            await db.flush()

            for row_num, account_code, account_name, description, debit, credit in valid_items:
                item = VoucherItem(
                    voucher_id=voucher.id,
                    account_code=account_code,
                    account_name=account_name,
                    description=description,
                    debit_amount=debit,
                    credit_amount=credit,
                )
                db.add(item)

            result.success_count += 1
        except Exception as e:
            for item in items:
                errors.append({"row": item["row"], "message": f"创建凭证失败: {str(e)}"})

    await db.commit()
    result.error_count = len(errors)
    result.errors = errors
    logger.info(f"用户 {current_user.username} 导入凭证: 成功 {result.success_count}, 失败 {result.error_count}")
    return result


# ========== 科目导入 ==========

@router.post("/import/accounts", response_model=ImportResult, summary="批量导入科目")
async def import_accounts(
    file: UploadFile = File(..., description="Excel 文件 (.xlsx)"),
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """从 Excel 文件批量导入/更新科目"""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传 .xlsx 格式的 Excel 文件")

    content = await file.read()
    try:
        rows = _read_excel_rows(content)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Excel 解析失败: {str(e)}")

    result = ImportResult(total_count=len(rows))
    errors = []

    for idx, row in enumerate(rows, start=2):
        account_code = row.get("account_code", "")
        account_name = row.get("account_name", "")
        account_type = row.get("account_type", "")
        parent_code = row.get("parent_code", "")
        balance_direction = row.get("balance_direction", "")

        if not account_code or not account_name or not account_type:
            errors.append({"row": idx, "message": "科目编码、科目名称和科目类型不能为空"})
            continue

        if balance_direction not in ("debit", "credit"):
            errors.append({"row": idx, "message": f"余额方向无效: {balance_direction}，应为 debit 或 credit"})
            continue

        if not parent_code:
            parent_code = None

        try:
            # Upsert: 查找是否存在
            existing = await db.execute(
                select(Account).where(Account.account_code == account_code)
            )
            account = existing.scalar_one_or_none()

            if account:
                account.account_name = account_name
                account.account_type = account_type
                account.parent_code = parent_code
                account.balance_direction = balance_direction
            else:
                account = Account(
                    account_code=account_code,
                    account_name=account_name,
                    account_type=account_type,
                    parent_code=parent_code,
                    balance_direction=balance_direction,
                    is_active=True,
                )
                db.add(account)

            result.success_count += 1
        except Exception as e:
            errors.append({"row": idx, "message": f"保存科目失败: {str(e)}"})

    await db.commit()
    result.error_count = len(errors)
    result.errors = errors
    logger.info(f"用户 {current_user.username} 导入科目: 成功 {result.success_count}, 失败 {result.error_count}")
    return result


# ========== 凭证导出 ==========

@router.get("/export/vouchers", summary="导出凭证为 Excel")
async def export_vouchers(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    status: Optional[str] = Query(None, description="按状态筛选"),
    current_user: User = Depends(require_permission("report:export")),
    db: AsyncSession = Depends(get_db),
):
    """导出凭证列表为 Excel 文件"""
    from openpyxl import Workbook

    query = select(Voucher).order_by(Voucher.voucher_date.desc(), Voucher.id.desc())
    filters = []
    if status:
        filters.append(Voucher.status == status)
    if start_date:
        filters.append(Voucher.voucher_date >= date.fromisoformat(start_date))
    if end_date:
        filters.append(Voucher.voucher_date <= date.fromisoformat(end_date))
    if filters:
        query = query.where(*filters)

    result = await db.execute(query)
    vouchers = result.scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "凭证列表"

    # 表头
    header_cols = [
        ("凭证号", 20), ("凭证日期", 15), ("摘要", 40), ("状态", 12),
        ("科目编码", 15), ("科目名称", 20), ("分录描述", 30),
        ("借方金额", 15), ("贷方金额", 15),
    ]
    for i, (h, w) in enumerate(header_cols, start=1):
        _style_header_cell(ws, 1, i, h, w)

    row_num = 2
    status_labels = {"draft": "草稿", "submitted": "已提交", "reviewed": "已审核", "posted": "已过账"}
    for voucher in vouchers:
        status_label = status_labels.get(voucher.status, voucher.status)
        vd = voucher.voucher_date.isoformat() if voucher.voucher_date else ""
        items = voucher.items if voucher.items else []
        if not items:
            _style_data_cell(ws, row_num, 1, voucher.voucher_no)
            _style_data_cell(ws, row_num, 2, vd)
            _style_data_cell(ws, row_num, 3, voucher.summary)
            _style_data_cell(ws, row_num, 4, status_label)
            for c in range(5, 10):
                _style_data_cell(ws, row_num, c, "")
            row_num += 1
        else:
            first = True
            for item in items:
                if first:
                    _style_data_cell(ws, row_num, 1, voucher.voucher_no)
                    _style_data_cell(ws, row_num, 2, vd)
                    _style_data_cell(ws, row_num, 3, voucher.summary)
                    _style_data_cell(ws, row_num, 4, status_label)
                    first = False
                else:
                    for c in range(1, 5):
                        _style_data_cell(ws, row_num, c, "")
                _style_data_cell(ws, row_num, 5, item.account_code)
                _style_data_cell(ws, row_num, 6, item.account_name)
                _style_data_cell(ws, row_num, 7, item.description)
                _style_data_cell(ws, row_num, 8, float(item.debit_amount), fmt="#,##0.00", is_number=True)
                _style_data_cell(ws, row_num, 9, float(item.credit_amount), fmt="#,##0.00", is_number=True)
                row_num += 1

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    filename = f"vouchers_{start_date or 'all'}_{end_date or 'all'}.xlsx"
    logger.info(f"用户 {current_user.username} 导出了凭证列表")
    return _build_excel_response(wb, filename)


# ========== 报表导出为 Excel ==========

@router.get("/export/report/{report_type}", summary="导出报表为 Excel")
async def export_report_xlsx(
    report_type: str,
    period: Optional[str] = Query(None, description="报表月份 YYYY-MM"),
    current_user: User = Depends(require_permission("report:export")),
    db: AsyncSession = Depends(get_db),
):
    """导出报表为格式化的 Excel 文件"""
    from openpyxl import Workbook

    valid_types = {"balance-sheet", "income-statement", "cash-flow", "account-ledger"}
    if report_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的报表类型，有效类型: {', '.join(valid_types)}",
        )

    start_date, end_date = _month_range(period)
    logger.info(f"用户 {current_user.username} 导出报表 Excel: {report_type}")

    wb = Workbook()
    ws = wb.active

    if report_type == "balance-sheet":
        ws.title = "资产负债表"
        await _export_balance_sheet_xlsx(ws, db, start_date, end_date)
    elif report_type == "income-statement":
        ws.title = "利润表"
        await _export_income_statement_xlsx(ws, db, start_date, end_date)
    elif report_type == "cash-flow":
        ws.title = "现金流量表"
        await _export_cash_flow_xlsx(ws, db, start_date, end_date)
    elif report_type == "account-ledger":
        ws.title = "科目余额表"
        await _export_account_ledger_xlsx(ws, db, start_date, end_date)

    filename = f"{report_type}_{period or 'report'}.xlsx"
    return _build_excel_response(wb, filename)


async def _export_balance_sheet_xlsx(ws, db, start_date, end_date):
    """导出资产负债表为 Excel"""
    from openpyxl.styles import Font, Alignment

    accounts = await _get_all_accounts(db)
    balances = await _get_account_balances(db, end_date)

    # 标题行
    ws.merge_cells("A1:C1")
    title_cell = ws.cell(row=1, column=1, value=f"资产负债表（{end_date}）")
    title_cell.font = Font(name="微软雅黑", bold=True, size=14)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    _style_header_cell(ws, 2, 1, "科目编码", 15)
    _style_header_cell(ws, 2, 2, "科目名称", 30)
    _style_header_cell(ws, 2, 3, "期末余额", 18)

    row = 3
    sections = {"asset": "资产", "liability": "负债", "equity": "所有者权益"}
    totals = {"asset": 0.0, "liability": 0.0, "equity": 0.0}

    for section_key, section_name in sections.items():
        ws.merge_cells(f"A{row}:C{row}")
        sec_cell = ws.cell(row=row, column=1, value=section_name)
        sec_cell.font = Font(name="微软雅黑", bold=True, size=11)
        sec_cell.alignment = Alignment(horizontal="left", vertical="center")
        row += 1

        for acc in accounts:
            if (
                (section_key == "asset" and acc.account_type == "asset")
                or (section_key == "liability" and acc.account_type == "liability")
                or (section_key == "equity" and acc.account_type == "equity")
            ):
                bal = balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
                if acc.balance_direction == "debit":
                    ending = bal["total_debit"] - bal["total_credit"]
                else:
                    ending = bal["total_credit"] - bal["total_debit"]
                _style_data_cell(ws, row, 1, acc.account_code)
                _style_data_cell(ws, row, 2, acc.account_name)
                _style_data_cell(ws, row, 3, round(ending, 2), fmt="#,##0.00", is_number=True)
                totals[section_key] += ending
                row += 1

        # 小计行
        _style_data_cell(ws, row, 1, "")
        sub_cell = ws.cell(row=row, column=2, value=f"{section_name}合计")
        sub_cell.font = Font(name="微软雅黑", bold=True, size=10)
        sub_cell.alignment = Alignment(horizontal="right", vertical="center")
        _style_data_cell(ws, row, 3, round(totals[section_key], 2), fmt="#,##0.00", is_number=True)
        row += 2

    ws.freeze_panes = "A3"


async def _export_income_statement_xlsx(ws, db, start_date, end_date):
    """导出利润表为 Excel"""
    from openpyxl.styles import Font, Alignment

    month_balances = await _get_account_balances(db, end_date, start_date)
    year_start = f"{end_date[:4]}-01-01"
    year_balances = await _get_account_balances(db, end_date, year_start)
    accounts = await _get_all_accounts(db)

    ws.merge_cells("A1:D1")
    title_cell = ws.cell(row=1, column=1, value=f"利润表（{start_date} ~ {end_date}）")
    title_cell.font = Font(name="微软雅黑", bold=True, size=14)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    _style_header_cell(ws, 2, 1, "科目编码", 15)
    _style_header_cell(ws, 2, 2, "科目名称", 30)
    _style_header_cell(ws, 2, 3, "本期金额", 18)
    _style_header_cell(ws, 2, 4, "本年累计金额", 18)

    row = 3
    for section_key, section_name in [("revenue", "收入"), ("expense", "费用")]:
        ws.merge_cells(f"A{row}:D{row}")
        sec_cell = ws.cell(row=row, column=1, value=section_name)
        sec_cell.font = Font(name="微软雅黑", bold=True, size=11)
        sec_cell.alignment = Alignment(horizontal="left", vertical="center")
        row += 1

        total_month = 0.0
        total_year = 0.0
        for acc in accounts:
            if acc.account_type != section_key:
                continue
            m_bal = month_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
            y_bal = year_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
            if acc.balance_direction == "credit":
                month_amt = m_bal["total_credit"] - m_bal["total_debit"]
                year_amt = y_bal["total_credit"] - y_bal["total_debit"]
            else:
                month_amt = m_bal["total_debit"] - m_bal["total_credit"]
                year_amt = y_bal["total_debit"] - y_bal["total_credit"]
            _style_data_cell(ws, row, 1, acc.account_code)
            _style_data_cell(ws, row, 2, acc.account_name)
            _style_data_cell(ws, row, 3, round(month_amt, 2), fmt="#,##0.00", is_number=True)
            _style_data_cell(ws, row, 4, round(year_amt, 2), fmt="#,##0.00", is_number=True)
            total_month += month_amt
            total_year += year_amt
            row += 1

        _style_data_cell(ws, row, 1, "")
        sub_cell = ws.cell(row=row, column=2, value=f"{section_name}合计")
        sub_cell.font = Font(name="微软雅黑", bold=True, size=10)
        sub_cell.alignment = Alignment(horizontal="right", vertical="center")
        _style_data_cell(ws, row, 3, round(total_month, 2), fmt="#,##0.00", is_number=True)
        _style_data_cell(ws, row, 4, round(total_year, 2), fmt="#,##0.00", is_number=True)
        row += 2

    ws.freeze_panes = "A3"


async def _export_cash_flow_xlsx(ws, db, start_date, end_date):
    """导出现金流量表为 Excel"""
    from openpyxl.styles import Font, Alignment

    balances = await _get_account_balances(db, end_date, start_date)
    accounts = await _get_all_accounts(db)
    cash_codes = {"1001", "1002", "1012", "1101"}

    ws.merge_cells("A1:C1")
    title_cell = ws.cell(row=1, column=1, value=f"现金流量表（{start_date} ~ {end_date}）")
    title_cell.font = Font(name="微软雅黑", bold=True, size=14)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    _style_header_cell(ws, 2, 1, "科目编码", 15)
    _style_header_cell(ws, 2, 2, "科目名称", 30)
    _style_header_cell(ws, 2, 3, "金额", 18)

    row = 3
    for section_name in ["经营活动", "投资活动", "筹资活动"]:
        ws.merge_cells(f"A{row}:C{row}")
        sec_cell = ws.cell(row=row, column=1, value=section_name)
        sec_cell.font = Font(name="微软雅黑", bold=True, size=11)
        sec_cell.alignment = Alignment(horizontal="left", vertical="center")
        row += 1

        for acc in accounts:
            if acc.account_code[:4] not in cash_codes:
                continue
            bal = balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
            net_flow = bal["total_debit"] - bal["total_credit"]
            _style_data_cell(ws, row, 1, acc.account_code)
            _style_data_cell(ws, row, 2, acc.account_name)
            _style_data_cell(ws, row, 3, round(net_flow, 2), fmt="#,##0.00", is_number=True)
            row += 1
        row += 1

    ws.freeze_panes = "A3"


async def _export_account_ledger_xlsx(ws, db, start_date, end_date):
    """导出科目余额表为 Excel"""
    from openpyxl.styles import Font, Alignment

    day_before = (date.fromisoformat(start_date) - timedelta(days=1)).isoformat()
    opening_balances = await _get_account_balances(db, day_before)
    period_balances = await _get_account_balances(db, end_date, start_date)
    accounts = await _get_all_accounts(db)

    ws.merge_cells("A1:H1")
    title_cell = ws.cell(row=1, column=1, value=f"科目余额表（{start_date} ~ {end_date}）")
    title_cell.font = Font(name="微软雅黑", bold=True, size=14)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")

    headers = [
        ("科目编码", 12), ("科目名称", 25),
        ("期初借方", 15), ("期初贷方", 15),
        ("本期借方", 15), ("本期贷方", 15),
        ("期末借方", 15), ("期末贷方", 15),
    ]
    for i, (h, w) in enumerate(headers, start=1):
        _style_header_cell(ws, 2, i, h, w)

    row = 3
    for acc in accounts:
        opening = opening_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})
        period = period_balances.get(acc.account_code, {"total_debit": 0, "total_credit": 0})

        if acc.balance_direction == "debit":
            beginning_debit = opening["total_debit"] - opening["total_credit"]
            beginning_credit = 0.0
        else:
            beginning_debit = 0.0
            beginning_credit = opening["total_credit"] - opening["total_debit"]

        current_debit = period["total_debit"]
        current_credit = period["total_credit"]
        ending_debit = beginning_debit + current_debit
        ending_credit = beginning_credit + current_credit

        if acc.balance_direction == "debit":
            net_ending = ending_debit - ending_credit
            e_debit = max(0.0, net_ending)
            e_credit = max(0.0, -net_ending)
        else:
            net_ending = ending_credit - ending_debit
            e_credit = max(0.0, net_ending)
            e_debit = max(0.0, -net_ending)

        _style_data_cell(ws, row, 1, acc.account_code)
        _style_data_cell(ws, row, 2, acc.account_name)
        _style_data_cell(ws, row, 3, round(beginning_debit, 2), fmt="#,##0.00", is_number=True)
        _style_data_cell(ws, row, 4, round(beginning_credit, 2), fmt="#,##0.00", is_number=True)
        _style_data_cell(ws, row, 5, round(current_debit, 2), fmt="#,##0.00", is_number=True)
        _style_data_cell(ws, row, 6, round(current_credit, 2), fmt="#,##0.00", is_number=True)
        _style_data_cell(ws, row, 7, round(e_debit, 2), fmt="#,##0.00", is_number=True)
        _style_data_cell(ws, row, 8, round(e_credit, 2), fmt="#,##0.00", is_number=True)
        row += 1

    ws.freeze_panes = "A3"


# ========== 数据库备份 ==========

@router.get("/export/backup", summary="数据库备份")
async def database_backup(
    current_user: User = Depends(require_permission("report:export")),
    db: AsyncSession = Depends(get_db),
):
    """导出所有数据为 JSON 备份文件"""
    # 导出科目
    acc_result = await db.execute(select(Account).order_by(Account.account_code))
    accounts = acc_result.scalars().all()

    # 导出凭证及分录
    v_result = await db.execute(
        select(Voucher).order_by(Voucher.voucher_date, Voucher.id)
    )
    vouchers = v_result.scalars().all()

    backup_data = {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "exported_by": current_user.username,
        "accounts": [
            {
                "account_code": a.account_code,
                "account_name": a.account_name,
                "account_type": a.account_type,
                "parent_code": a.parent_code,
                "balance_direction": a.balance_direction,
                "is_active": a.is_active,
            }
            for a in accounts
        ],
        "vouchers": [
            {
                "voucher_no": v.voucher_no,
                "voucher_date": v.voucher_date.isoformat() if v.voucher_date else "",
                "summary": v.summary,
                "status": v.status,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat() if v.created_at else "",
                "items": [
                    {
                        "account_code": i.account_code,
                        "account_name": i.account_name,
                        "description": i.description,
                        "debit_amount": float(i.debit_amount),
                        "credit_amount": float(i.credit_amount),
                    }
                    for i in (v.items or [])
                ],
            }
            for v in vouchers
        ],
    }

    json_str = json.dumps(backup_data, ensure_ascii=False, indent=2)
    filename = f"accounting_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    logger.info(f"用户 {current_user.username} 创建了数据库备份")
    return Response(
        content=json_str.encode("utf-8"),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ========== 数据恢复 ==========

class RestoreResult(BaseModel):
    """恢复结果"""
    accounts_count: int = 0
    vouchers_count: int = 0
    items_count: int = 0


@router.post("/import/restore", response_model=RestoreResult, summary="从备份恢复数据")
async def restore_backup(
    file: UploadFile = File(..., description="JSON 备份文件"),
    current_user: User = Depends(require_permission("voucher:delete")),
    db: AsyncSession = Depends(get_db),
):
    """从 JSON 备份文件恢复数据（会清除现有数据）"""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传 .json 格式的备份文件")

    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"JSON 解析失败: {str(e)}")

    if "version" not in data or "accounts" not in data or "vouchers" not in data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无效的备份文件格式")

    # 清除现有数据（先删除分录，再删除凭证，最后删除科目）
    await db.execute(delete(VoucherItem))
    await db.execute(delete(Voucher))
    await db.execute(delete(Account))
    await db.flush()

    # 恢复科目
    accounts_count = 0
    for acc in data.get("accounts", []):
        account = Account(
            account_code=acc["account_code"],
            account_name=acc["account_name"],
            account_type=acc["account_type"],
            parent_code=acc.get("parent_code"),
            balance_direction=acc["balance_direction"],
            is_active=acc.get("is_active", True),
        )
        db.add(account)
        accounts_count += 1

    await db.flush()

    # 恢复凭证
    vouchers_count = 0
    items_count = 0
    for v_data in data.get("vouchers", []):
        vd = v_data.get("voucher_date", "")
        voucher_date = date.fromisoformat(vd) if vd else date.today()
        voucher = Voucher(
            voucher_no=v_data["voucher_no"],
            voucher_date=voucher_date,
            summary=v_data["summary"],
            status=v_data.get("status", "draft"),
            created_by=current_user.id,
        )
        db.add(voucher)
        vouchers_count += 1
        await db.flush()

        for item_data in v_data.get("items", []):
            item = VoucherItem(
                voucher_id=voucher.id,
                account_code=item_data["account_code"],
                account_name=item_data["account_name"],
                description=item_data["description"],
                debit_amount=item_data.get("debit_amount", 0),
                credit_amount=item_data.get("credit_amount", 0),
            )
            db.add(item)
            items_count += 1

    await db.commit()
    logger.info(
        f"用户 {current_user.username} 从备份恢复了数据: "
        f"科目 {accounts_count}, 凭证 {vouchers_count}, 分录 {items_count}"
    )
    return RestoreResult(
        accounts_count=accounts_count,
        vouchers_count=vouchers_count,
        items_count=items_count,
    )