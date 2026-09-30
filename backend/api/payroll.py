"""
工资管理 API
工资项目 CRUD + 工资记录管理 + 凭证生成
"""
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.payroll import SalaryItem, SalaryRecord
from models.voucher import Voucher, VoucherItem, Account
from auth.middleware import get_current_user
from auth.book_context import get_current_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["工资管理"])


# ========== 请求/响应模型 ==========

class SalaryItemCreate(BaseModel):
    name: str = Field(..., description="项目名称")
    item_type: str = Field(..., description="项目类型: income/deduction")
    formula: Optional[str] = Field(default=None, description="计算公式")
    sort_order: int = Field(default=0, description="排序序号")


class SalaryItemUpdate(BaseModel):
    name: Optional[str] = None
    item_type: Optional[str] = None
    formula: Optional[str] = None
    sort_order: Optional[int] = None


class SalaryRecordCreate(BaseModel):
    employee_name: str = Field(..., description="员工姓名")
    employee_code: Optional[str] = Field(default=None, description="员工编号")
    period: str = Field(..., description="工资期间: YYYY-MM")
    salary_data: dict = Field(default={}, description="工资数据")


class SalaryRecordBatch(BaseModel):
    period: str = Field(..., description="工资期间")
    employee_names: list[str] = Field(..., description="员工姓名列表")
    salary_data_template: Optional[dict] = Field(default=None, description="工资数据模板")


class SalaryRecordUpdate(BaseModel):
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    salary_data: Optional[dict] = None
    total_income: Optional[float] = None
    total_deduction: Optional[float] = None
    net_salary: Optional[float] = None


class GenerateVoucherRequest(BaseModel):
    record_ids: list[int] = Field(..., description="工资记录ID列表")


# ========== 工资项目管理 ==========

@router.get("/salary-items", summary="获取工资项目列表")
async def list_salary_items(
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取工资项目列表"""
    book_id = current_book.id
    query = select(SalaryItem).where(SalaryItem.book_id == book_id).order_by(SalaryItem.sort_order, SalaryItem.id)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "item_type": item.item_type,
                "formula": item.formula,
                "sort_order": item.sort_order,
                "book_id": item.book_id,
            }
            for item in items
        ]
    }


@router.post("/salary-items", summary="添加工资项目")
async def create_salary_item(
    req: SalaryItemCreate,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """添加新工资项目"""
    book_id = current_book.id
    if req.item_type not in ("income", "deduction"):
        raise HTTPException(status_code=400, detail="项目类型必须为 income 或 deduction")

    item = SalaryItem(
        name=req.name,
        item_type=req.item_type,
        formula=req.formula,
        sort_order=req.sort_order,
        book_id=book_id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"message": "添加成功", "id": item.id}


@router.put("/salary-items/{item_id}", summary="更新工资项目")
async def update_salary_item(
    item_id: int,
    req: SalaryItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新工资项目"""
    result = await db.execute(
        select(SalaryItem).where(SalaryItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="工资项目不存在")

    if req.name is not None:
        item.name = req.name
    if req.item_type is not None:
        if req.item_type not in ("income", "deduction"):
            raise HTTPException(status_code=400, detail="项目类型必须为 income 或 deduction")
        item.item_type = req.item_type
    if req.formula is not None:
        item.formula = req.formula
    if req.sort_order is not None:
        item.sort_order = req.sort_order

    await db.commit()
    return {"message": "更新成功"}


@router.delete("/salary-items/{item_id}", summary="删除工资项目")
async def delete_salary_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除工资项目"""
    result = await db.execute(
        select(SalaryItem).where(SalaryItem.id == item_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="工资项目不存在")

    await db.delete(item)
    await db.commit()
    return {"message": "删除成功"}


# ========== 工资记录管理 ==========

@router.get("/salary-records", summary="获取工资记录列表")
async def list_salary_records(
    period: Optional[str] = Query(None, description="工资期间: YYYY-MM"),
    employee_name: Optional[str] = Query(None, description="员工姓名"),
    status: Optional[str] = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取工资记录列表"""
    book_id = current_book.id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    conditions = [SalaryRecord.book_id == book_id]
    if period:
        conditions.append(SalaryRecord.period == period)
    if employee_name:
        conditions.append(SalaryRecord.employee_name.ilike(f"%{employee_name}%"))
    if status:
        conditions.append(SalaryRecord.status == status)

    count_query = select(func.count()).select_from(SalaryRecord).where(and_(*conditions))
    total = (await db.execute(count_query)).scalar()

    query = (
        select(SalaryRecord)
        .where(and_(*conditions))
        .order_by(SalaryRecord.employee_name, SalaryRecord.period.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    records = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "employee_name": r.employee_name,
                "employee_code": r.employee_code,
                "period": r.period,
                "salary_data": r.salary_data,
                "total_income": float(r.total_income),
                "total_deduction": float(r.total_deduction),
                "net_salary": float(r.net_salary),
                "status": r.status,
                "book_id": r.book_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }


@router.post("/salary-records", summary="创建工资记录")
async def create_salary_record(
    req: SalaryRecordCreate,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """创建单条工资记录"""
    book_id = current_book.id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    # 检查是否已存在
    existing = await db.execute(
        select(SalaryRecord).where(
            SalaryRecord.book_id == book_id,
            SalaryRecord.employee_name == req.employee_name,
            SalaryRecord.period == req.period,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"员工 {req.employee_name} 在 {req.period} 期间已有工资记录"
        )

    record = SalaryRecord(
        employee_name=req.employee_name,
        employee_code=req.employee_code,
        period=req.period,
        salary_data=req.salary_data or {},
        total_income=Decimal("0"),
        total_deduction=Decimal("0"),
        net_salary=Decimal("0"),
        status="draft",
        book_id=book_id,
        created_by=current_user.id,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {"message": "创建成功", "id": record.id}


@router.put("/salary-records/{record_id}", summary="更新工资记录")
async def update_salary_record(
    record_id: int,
    req: SalaryRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新工资记录"""
    result = await db.execute(
        select(SalaryRecord).where(SalaryRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="工资记录不存在")

    if record.status != "draft":
        raise HTTPException(status_code=400, detail="只能修改草稿状态的工资记录")

    if req.employee_name is not None:
        record.employee_name = req.employee_name
    if req.employee_code is not None:
        record.employee_code = req.employee_code
    if req.salary_data is not None:
        record.salary_data = req.salary_data
    if req.total_income is not None:
        record.total_income = Decimal(str(req.total_income))
    if req.total_deduction is not None:
        record.total_deduction = Decimal(str(req.total_deduction))
    if req.net_salary is not None:
        record.net_salary = Decimal(str(req.net_salary))

    await db.commit()
    return {"message": "更新成功"}


@router.post("/salary-records/batch", summary="批量导入工资")
async def batch_import_salary(
    req: SalaryRecordBatch,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """批量创建员工工资记录"""
    book_id = current_book.id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    imported = 0
    skipped = 0
    template = req.salary_data_template or {}

    for name in req.employee_names:
        name = name.strip()
        if not name:
            continue

        existing = await db.execute(
            select(SalaryRecord).where(
                SalaryRecord.book_id == book_id,
                SalaryRecord.employee_name == name,
                SalaryRecord.period == req.period,
            )
        )
        if existing.scalar_one_or_none():
            skipped += 1
            continue

        db.add(SalaryRecord(
            employee_name=name,
            period=req.period,
            salary_data=template.copy(),
            total_income=Decimal("0"),
            total_deduction=Decimal("0"),
            net_salary=Decimal("0"),
            status="draft",
            book_id=book_id,
            created_by=current_user.id,
        ))
        imported += 1

    await db.commit()
    return {
        "message": f"导入完成: 成功 {imported} 条, 跳过 {skipped} 条",
        "imported": imported,
        "skipped": skipped,
    }


@router.post("/salary-records/{record_id}/confirm", summary="确认工资")
async def confirm_salary(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """确认工资记录"""
    result = await db.execute(
        select(SalaryRecord).where(SalaryRecord.id == record_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="工资记录不存在")

    if record.status == "confirmed":
        raise HTTPException(status_code=400, detail="该工资记录已确认")
    if record.status == "paid":
        raise HTTPException(status_code=400, detail="该工资记录已发放")

    record.status = "confirmed"
    await db.commit()
    return {"message": "确认成功"}


@router.post("/salary-records/generate-voucher", summary="生成工资凭证")
async def generate_salary_voucher(
    req: GenerateVoucherRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """根据工资记录生成计提工资和发放工资凭证"""
    book_id = current_book.id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    if not req.record_ids:
        raise HTTPException(status_code=400, detail="请选择工资记录")

    result = await db.execute(
        select(SalaryRecord).where(
            SalaryRecord.id.in_(req.record_ids),
            SalaryRecord.book_id == book_id,
        )
    )
    records = result.scalars().all()
    if not records:
        raise HTTPException(status_code=404, detail="未找到工资记录")

    # 获取工资项目和科目
    items_result = await db.execute(
        select(SalaryItem).where(SalaryItem.book_id == book_id)
    )
    salary_items = items_result.scalars().all()

    # 获取科目
    accounts_result = await db.execute(
        select(Account).where(Account.book_id == book_id)
    )
    accounts = {a.account_code: a for a in accounts_result.scalars().all()}

    # 计算汇总
    total_salary = Decimal("0")
    total_social_insurance = Decimal("0")
    total_housing_fund = Decimal("0")
    total_tax = Decimal("0")

    for record in records:
        total_salary += record.total_income
        data = record.salary_data or {}
        for key, val in data.items():
            val = Decimal(str(val)) if val else Decimal("0")
            if "社保" in key:
                total_social_insurance += val
            elif "公积金" in key:
                total_housing_fund += val
            elif "个税" in key or "所得税" in key:
                total_tax += val

    period = records[0].period
    voucher_date = date.today()

    # 获取凭证号
    count_result = await db.execute(
        select(func.count()).select_from(Voucher).where(Voucher.book_id == book_id)
    )
    count = (count_result.scalar() or 0) + 1

    generated_vouchers = []

    # ===== 凭证1: 计提工资 =====
    voucher_no = f"记-{count}"
    count += 1
    voucher1 = Voucher(
        voucher_type="记",
        voucher_no=voucher_no,
        voucher_date=voucher_date,
        summary=f"计提{period}工资",
        status="draft",
        book_id=book_id,
        created_by=current_user.id,
    )
    db.add(voucher1)
    await db.flush()

    # 借方: 管理费用-工资
    db.add(VoucherItem(
        voucher_id=voucher1.id,
        account_code="6602",
        account_name="管理费用-工资",
        description=f"计提{period}工资",
        debit_amount=total_salary,
        credit_amount=Decimal("0"),
        sort_order=1,
    ))
    # 贷方: 应付职工薪酬
    db.add(VoucherItem(
        voucher_id=voucher1.id,
        account_code="2211",
        account_name="应付职工薪酬",
        description=f"计提{period}工资",
        debit_amount=Decimal("0"),
        credit_amount=total_salary,
        sort_order=2,
    ))
    generated_vouchers.append({"voucher_no": voucher_no, "type": "计提工资", "amount": float(total_salary)})

    # ===== 凭证2: 发放工资 =====
    voucher_no = f"记-{count}"
    voucher2 = Voucher(
        voucher_type="记",
        voucher_no=voucher_no,
        voucher_date=voucher_date,
        summary=f"发放{period}工资",
        status="draft",
        book_id=book_id,
        created_by=current_user.id,
    )
    db.add(voucher2)
    await db.flush()

    sort_order = 1
    # 借方: 应付职工薪酬
    db.add(VoucherItem(
        voucher_id=voucher2.id,
        account_code="2211",
        account_name="应付职工薪酬",
        description=f"发放{period}工资",
        debit_amount=total_salary,
        credit_amount=Decimal("0"),
        sort_order=sort_order,
    ))
    sort_order += 1

    # 贷方: 银行存款（实发部分）
    net_pay = total_salary - total_social_insurance - total_housing_fund - total_tax
    db.add(VoucherItem(
        voucher_id=voucher2.id,
        account_code="1002",
        account_name="银行存款",
        description=f"发放{period}工资-实发",
        debit_amount=Decimal("0"),
        credit_amount=net_pay,
        sort_order=sort_order,
    ))
    sort_order += 1

    # 贷方: 其他应付款-社保
    if total_social_insurance > 0:
        db.add(VoucherItem(
            voucher_id=voucher2.id,
            account_code="2241",
            account_name="其他应付款-社保",
            description=f"代扣{period}社保",
            debit_amount=Decimal("0"),
            credit_amount=total_social_insurance,
            sort_order=sort_order,
        ))
        sort_order += 1

    # 贷方: 其他应付款-公积金
    if total_housing_fund > 0:
        db.add(VoucherItem(
            voucher_id=voucher2.id,
            account_code="2241",
            account_name="其他应付款-公积金",
            description=f"代扣{period}公积金",
            debit_amount=Decimal("0"),
            credit_amount=total_housing_fund,
            sort_order=sort_order,
        ))
        sort_order += 1

    # 贷方: 应交税费-个人所得税
    if total_tax > 0:
        db.add(VoucherItem(
            voucher_id=voucher2.id,
            account_code="2221",
            account_name="应交税费-个人所得税",
            description=f"代扣{period}个税",
            debit_amount=Decimal("0"),
            credit_amount=total_tax,
            sort_order=sort_order,
        ))
        sort_order += 1

    generated_vouchers.append({"voucher_no": voucher_no, "type": "发放工资", "amount": float(total_salary)})

    # 更新工资记录状态
    for record in records:
        record.status = "paid"

    await db.commit()

    return {
        "message": f"成功生成 {len(generated_vouchers)} 张凭证",
        "vouchers": generated_vouchers,
        "summary": {
            "period": period,
            "employee_count": len(records),
            "total_salary": float(total_salary),
            "net_pay": float(net_pay),
            "social_insurance": float(total_social_insurance),
            "housing_fund": float(total_housing_fund),
            "tax": float(total_tax),
        },
    }