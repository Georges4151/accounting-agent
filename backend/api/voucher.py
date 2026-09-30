"""
凭证管理 API 路由
提供凭证的 CRUD、审核和 AI 生成功能
"""
import logging
from typing import Optional, List
from datetime import date, datetime
import os
import json
import shutil

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.voucher import Voucher, VoucherItem, Account
from auth.middleware import get_current_user, require_permission
from auth.book_context import get_current_book
from utils.data_mask import (
    mask_voucher_list, mask_voucher_response,
    mask_amount, should_mask,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/vouchers", tags=["凭证管理"])


# ========== 请求/响应模型 ==========

class VoucherItemCreate(BaseModel):
    """凭证分录创建体"""
    account_code: str = Field(..., description="科目编码")
    account_name: str = Field(..., description="科目名称")
    description: str = Field(..., description="分录描述")
    debit_amount: float = Field(default=0, description="借方金额")
    credit_amount: float = Field(default=0, description="贷方金额")
    cash_flow_tag: Optional[str] = Field(None, description="现金流量标记")
    auxiliary_accounting: Optional[dict] = Field(None, description="辅助核算")


class VoucherCreate(BaseModel):
    """创建凭证请求体"""
    voucher_type: str = Field(default="记", description="凭证字: 记/转/收/付")
    voucher_date: str = Field(..., description="凭证日期 YYYY-MM-DD")
    summary: str = Field(..., description="摘要")
    items: List[VoucherItemCreate] = Field(..., min_length=2, description="分录列表")


class VoucherUpdate(BaseModel):
    """更新凭证请求体"""
    voucher_type: Optional[str] = Field(None, description="凭证字")
    voucher_date: Optional[str] = Field(None, description="凭证日期")
    summary: Optional[str] = Field(None, description="摘要")
    items: Optional[List[VoucherItemCreate]] = Field(None, description="分录列表")


class VoucherItemResponse(BaseModel):
    """凭证分录响应体"""
    id: int
    account_code: str
    account_name: str
    description: str
    debit_amount: float
    credit_amount: float
    cash_flow_tag: Optional[str] = None
    auxiliary_accounting: Optional[dict] = None

    class Config:
        from_attributes = True


class VoucherResponse(BaseModel):
    """凭证详情响应体"""
    id: int
    voucher_type: str = "记"
    voucher_no: str
    voucher_date: str
    summary: str
    status: str
    created_by: int
    reviewed_by: Optional[int] = None
    cashier_reviewed: bool = False
    cashier_reviewed_by: Optional[int] = None
    cashier_reviewed_at: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[str] = None
    posted_at: Optional[str] = None
    created_at: Optional[str] = None
    items: List[VoucherItemResponse]

    class Config:
        from_attributes = True


class VoucherListItem(BaseModel):
    """凭证列表项"""
    id: int
    voucher_type: str = "记"
    voucher_no: str
    voucher_date: str
    summary: str
    status: str
    total_debit: float = 0
    total_credit: float = 0
    created_by: int
    created_by_name: Optional[str] = None
    reviewed_by: Optional[int] = None
    cashier_reviewed: bool = False
    approved_by: Optional[int] = None
    created_at: Optional[str]
    attachment_count: int = 0

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """分页响应"""
    total: int
    page: int
    page_size: int
    items: List[VoucherListItem]


class AiGenerateRequest(BaseModel):
    """AI 生成凭证请求体"""
    description: str = Field(..., min_length=1, description="自然语言描述")
    voucher_date: Optional[str] = Field(None, description="凭证日期 YYYY-MM-DD")


class ReviewRequest(BaseModel):
    """审核请求体"""
    comment: Optional[str] = Field(None, description="审核意见")


class BatchRequest(BaseModel):
    """批量操作请求体"""
    voucher_ids: List[int] = Field(..., min_length=1, description="凭证ID列表")
    comment: Optional[str] = Field(None, description="审核意见")


class BatchStatusRequest(BaseModel):
    """批量状态更新请求体"""
    voucher_ids: List[int] = Field(..., min_length=1, description="凭证ID列表")
    target_status: str = Field(..., description="目标状态: draft/submitted/reviewed/rejected")


class BatchResultItem(BaseModel):
    """批量操作结果单项"""
    id: int
    status: str = "success"
    error: Optional[str] = None


class BatchResult(BaseModel):
    """批量操作结果"""
    success_count: int = 0
    failed_count: int = 0
    results: List[BatchResultItem] = []


# ========== 辅助函数 ==========

async def _generate_voucher_no(voucher_type: str, db: AsyncSession) -> str:
    """按凭证字+月份自动生成凭证号，格式: 记-2026-08-001"""
    from sqlalchemy import extract
    now = datetime.now()
    month_prefix = f"{voucher_type}-{now.strftime('%Y-%m')}-"
    
    # 查询当月该类型最大凭证号
    result = await db.execute(
        select(Voucher.voucher_no)
        .where(
            Voucher.voucher_type == voucher_type,
            Voucher.voucher_no.like(f"{month_prefix}%"),
        )
        .order_by(Voucher.voucher_no.desc())
        .limit(1)
    )
    last_no = result.scalar_one_or_none()
    
    if last_no:
        try:
            seq = int(last_no.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    
    return f"{month_prefix}{seq:03d}"


# ========== API 端点 ==========

@router.get("", response_model=PaginatedResponse, summary="凭证列表")
async def list_vouchers(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="按状态筛选，支持逗号分隔多个值: draft/submitted/reviewed/approved/posted"),
    voucher_type: Optional[str] = Query(None, description="按凭证字筛选: 记/转/收/付"),
    keyword: Optional[str] = Query(None, description="搜索关键词（凭证号/摘要）"),
    voucher_no: Optional[str] = Query(None, description="凭证号精确搜索"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_order: Optional[str] = Query("desc", description="排序方向: asc/desc"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取凭证列表，支持分页和筛选"""
    query = select(Voucher)
    count_query = select(func.count(Voucher.id))

    filters = []
    # 按账套过滤
    filters.append(Voucher.book_id == current_book.id)
    if status:
        status_list = [s.strip() for s in status.split(",") if s.strip()]
        if len(status_list) == 1:
            filters.append(Voucher.status == status_list[0])
        else:
            filters.append(Voucher.status.in_(status_list))
    if keyword:
        filters.append(
            (Voucher.voucher_no.ilike(f"%{keyword}%"))
            | (Voucher.summary.ilike(f"%{keyword}%"))
        )
    if voucher_no:
        filters.append(Voucher.voucher_no.ilike(f"%{voucher_no}%"))
    if voucher_type:
        filters.append(Voucher.voucher_type == voucher_type)
    if start_date:
        filters.append(Voucher.voucher_date >= date.fromisoformat(start_date))
    if end_date:
        filters.append(Voucher.voucher_date <= date.fromisoformat(end_date))

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size

    # 排序逻辑
    sort_column = Voucher.id
    if sort_by:
        sort_map = {
            "voucher_no": Voucher.voucher_no,
            "voucher_date": Voucher.voucher_date,
            "status": Voucher.status,
            "total_debit": Voucher.id,  # 前端排序，后端按id
            "total_credit": Voucher.id,  # 前端排序，后端按id
        }
        sort_column = sort_map.get(sort_by, Voucher.id)

    if sort_order == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    vouchers = result.scalars().all()

    # 查询每个凭证的借方/贷方合计
    voucher_ids = [v.id for v in vouchers]
    items = []
    user_role = current_user.role  # 确保在所有代码路径中都有定义
    if voucher_ids:
        # 批量查询分录合计
        totals_query = (
            select(
                VoucherItem.voucher_id,
                func.coalesce(func.sum(VoucherItem.debit_amount), 0).label("total_debit"),
                func.coalesce(func.sum(VoucherItem.credit_amount), 0).label("total_credit"),
            )
            .where(VoucherItem.voucher_id.in_(voucher_ids))
            .group_by(VoucherItem.voucher_id)
        )
        totals_result = await db.execute(totals_query)
        totals_map = {row.voucher_id: (float(row.total_debit), float(row.total_credit)) for row in totals_result.all()}

        # 批量查询用户名
        user_ids = list(set(v.created_by for v in vouchers))
        user_query = select(User.id, User.username).where(User.id.in_(user_ids))
        user_result = await db.execute(user_query)
        user_map = {row.id: row.username for row in user_result.all()}

        for v in vouchers:
            td, tc = totals_map.get(v.id, (0, 0))
            item = dict(
                id=v.id,
                voucher_type=v.voucher_type,
                voucher_no=v.voucher_no,
                voucher_date=v.voucher_date.isoformat() if v.voucher_date else "",
                summary=v.summary,
                status=v.status,
                total_debit=td,
                total_credit=tc,
                created_by=v.created_by,
                created_by_name=user_map.get(v.created_by),
                reviewed_by=v.reviewed_by,
                cashier_reviewed=v.cashier_reviewed,
                approved_by=v.approved_by,
                created_at=v.created_at.isoformat() if v.created_at else None,
                attachment_count=len(v.attachments) if v.attachments else 0,
            )
            items.append(item)

    # 应用金额脱敏
    items = mask_voucher_list(items, user_role)

    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.post("", response_model=VoucherResponse, summary="创建凭证")
async def create_voucher(
    voucher_data: VoucherCreate,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """创建新的记账凭证"""
    # 校验借贷平衡
    total_debit = sum(item.debit_amount for item in voucher_data.items)
    total_credit = sum(item.credit_amount for item in voucher_data.items)
    if abs(total_debit - total_credit) > 0.01:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"借贷不平衡: 借方={total_debit}, 贷方={total_credit}",
        )

    # 创建凭证
    voucher = Voucher(
        voucher_type=voucher_data.voucher_type,
        voucher_no=await _generate_voucher_no(voucher_data.voucher_type, db),
        voucher_date=date.fromisoformat(voucher_data.voucher_date),
        summary=voucher_data.summary,
        status="draft",
        created_by=current_user.id,
    )
    db.add(voucher)
    await db.flush()

    # 创建分录
    for item_data in voucher_data.items:
        item = VoucherItem(
            voucher_id=voucher.id,
            account_code=item_data.account_code,
            account_name=item_data.account_name,
            description=item_data.description,
            debit_amount=item_data.debit_amount,
            credit_amount=item_data.credit_amount,
            cash_flow_tag=item_data.cash_flow_tag,
            auxiliary_accounting=item_data.auxiliary_accounting,
        )
        db.add(item)

    await db.commit()
    await db.refresh(voucher)
    logger.info(f"用户 {current_user.username} 创建了凭证 {voucher.voucher_no}")

    return VoucherResponse(
        id=voucher.id,
        voucher_type=voucher.voucher_type,
        voucher_no=voucher.voucher_no,
        voucher_date=voucher.voucher_date.isoformat(),
        summary=voucher.summary,
        status=voucher.status,
        created_by=voucher.created_by,
        reviewed_by=voucher.reviewed_by,
        cashier_reviewed=voucher.cashier_reviewed,
        cashier_reviewed_by=voucher.cashier_reviewed_by,
        cashier_reviewed_at=voucher.cashier_reviewed_at.isoformat() if voucher.cashier_reviewed_at else None,
        approved_by=voucher.approved_by,
        approved_at=voucher.approved_at.isoformat() if voucher.approved_at else None,
        posted_at=voucher.posted_at.isoformat() if voucher.posted_at else None,
        created_at=voucher.created_at.isoformat() if voucher.created_at else None,
        items=[
            VoucherItemResponse(
                id=i.id,
                account_code=i.account_code,
                account_name=i.account_name,
                description=i.description,
                debit_amount=float(i.debit_amount),
                credit_amount=float(i.credit_amount),
                cash_flow_tag=i.cash_flow_tag,
                auxiliary_accounting=i.auxiliary_accounting,
            )
            for i in voucher.items
        ],
    )


# ========== 凭证台账 ==========

class LedgerItem(BaseModel):
    """台账分录项"""
    voucher_id: int
    voucher_no: str
    voucher_type: str
    voucher_date: str
    voucher_summary: str
    status: str
    account_code: str
    account_name: str
    description: str
    debit_amount: float
    credit_amount: float
    cash_flow_tag: Optional[str] = None
    created_by_name: str


class LedgerResponse(BaseModel):
    """台账响应"""
    items: list[LedgerItem]
    total: int
    total_debit: float
    total_credit: float
    page: int
    page_size: int


@router.get("/ledger", response_model=LedgerResponse, summary="凭证台账")
async def get_voucher_ledger(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    account_code: Optional[str] = Query(None, description="科目代码筛选"),
    voucher_type: Optional[str] = Query(None, description="凭证字: 记/转/收/付"),
    status: Optional[str] = Query(None, description="状态筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索（凭证号/摘要）"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """凭证台账：以分录为行展示，支持按科目/时间/凭证字筛选，附带汇总统计"""
    # 构建基础查询：联结 voucher + voucher_items
    from sqlalchemy.orm import joinedload

    # 计数查询
    count_conditions = [
        Voucher.book_id == current_book.id,
        VoucherItem.voucher_id == Voucher.id,
    ]
    list_conditions = [Voucher.book_id == current_book.id]

    if start_date:
        count_conditions.append(Voucher.voucher_date >= date.fromisoformat(start_date))
        list_conditions.append(Voucher.voucher_date >= date.fromisoformat(start_date))
    if end_date:
        count_conditions.append(Voucher.voucher_date <= date.fromisoformat(end_date))
        list_conditions.append(Voucher.voucher_date <= date.fromisoformat(end_date))
    if account_code:
        count_conditions.append(VoucherItem.account_code == account_code)
        list_conditions.append(VoucherItem.account_code == account_code)
    if voucher_type:
        count_conditions.append(Voucher.voucher_type == voucher_type)
        list_conditions.append(Voucher.voucher_type == voucher_type)
    if status:
        count_conditions.append(Voucher.status == status)
        list_conditions.append(Voucher.status == status)
    if keyword:
        kw_filter = (Voucher.voucher_no.ilike(f"%{keyword}%")) | (Voucher.summary.ilike(f"%{keyword}%"))
        count_conditions.append(kw_filter)
        list_conditions.append(kw_filter)

    # 计数
    count_query = (
        select(func.count(VoucherItem.id))
        .select_from(VoucherItem)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(*count_conditions)
    )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # 汇总统计（全部数据，不受分页影响）
    summary_query = (
        select(
            func.coalesce(func.sum(VoucherItem.debit_amount), 0),
            func.coalesce(func.sum(VoucherItem.credit_amount), 0),
        )
        .select_from(VoucherItem)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(*count_conditions)
    )
    summary_result = await db.execute(summary_query)
    summary_row = summary_result.first()
    total_debit = float(summary_row[0]) if summary_row else 0
    total_credit = float(summary_row[1]) if summary_row else 0

    # 分页查询
    offset = (page - 1) * page_size
    items_query = (
        select(
            Voucher.id.label("voucher_id"),
            Voucher.voucher_no,
            Voucher.voucher_type,
            Voucher.voucher_date,
            Voucher.summary.label("voucher_summary"),
            Voucher.status,
            VoucherItem.account_code,
            VoucherItem.account_name,
            VoucherItem.description,
            VoucherItem.debit_amount,
            VoucherItem.credit_amount,
            VoucherItem.cash_flow_tag,
            User.real_name.label("created_by_name"),
        )
        .select_from(VoucherItem)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .outerjoin(User, Voucher.created_by == User.id)
        .where(*list_conditions)
        .order_by(Voucher.voucher_date.desc(), Voucher.voucher_no.desc(), VoucherItem.id)
        .offset(offset)
        .limit(page_size)
    )
    items_result = await db.execute(items_query)
    rows = items_result.all()

    items = []
    for row in rows:
        items.append(LedgerItem(
            voucher_id=row.voucher_id,
            voucher_no=row.voucher_no,
            voucher_type=row.voucher_type,
            voucher_date=str(row.voucher_date),
            voucher_summary=row.voucher_summary or "",
            status=row.status,
            account_code=row.account_code,
            account_name=row.account_name,
            description=row.description or "",
            debit_amount=float(row.debit_amount or 0),
            credit_amount=float(row.credit_amount or 0),
            cash_flow_tag=row.cash_flow_tag,
            created_by_name=row.created_by_name or "",
        ))

    return LedgerResponse(
        items=items,
        total=total,
        total_debit=total_debit,
        total_credit=total_credit,
        page=page,
        page_size=page_size,
    )


# ========== 科目查询 ==========

@router.get("/accounts", summary="获取科目列表")
async def list_accounts(
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取所有可用科目，供前端下拉选择"""
    result = await db.execute(
        select(Account).where(
            Account.is_active == True,
            Account.book_id == current_book.id,
        ).order_by(Account.account_code)
    )
    accounts = result.scalars().all()

    return {
        "accounts": [
            {
                "id": acc.id,
                "code": acc.account_code,
                "name": acc.account_name,
                "account_type": acc.account_type,
                "balance_direction": acc.balance_direction,
            }
            for acc in accounts
        ],
    }


@router.get("/accounts/tree", summary="获取科目树")
async def get_accounts_tree(
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取科目树形结构，按 parent_code 递归组织"""
    result = await db.execute(
        select(Account).where(
            Account.is_active == True,
            Account.book_id == current_book.id,
        ).order_by(Account.account_code)
    )
    accounts = result.scalars().all()

    # 构建科目字典
    account_map = {}
    for acc in accounts:
        account_map[acc.account_code] = {
            "code": acc.account_code,
            "name": acc.account_name,
            "type": acc.account_type,
            "parent_code": acc.parent_code,
            "level": len(acc.account_code) // 2 - 1 if len(acc.account_code) >= 4 else 0,
            "children": [],
        }

    # 构建树
    roots = []
    for acc in account_map.values():
        parent = acc["parent_code"]
        if parent and parent in account_map:
            account_map[parent]["children"].append(acc)
        else:
            roots.append(acc)

    return {"tree": roots}


# ========== 批量操作状态预览 ==========

class BatchStatusPreviewItem(BaseModel):
    """批量状态预览单项"""
    voucher_id: int
    voucher_no: str
    current_status: str
    can_submit: bool = False
    can_review: bool = False
    can_approve: bool = False
    can_reject: bool = False
    can_delete: bool = False


class BatchStatusPreview(BaseModel):
    """批量状态预览"""
    total: int
    eligible_submit: int = 0
    eligible_review: int = 0
    eligible_approve: int = 0
    eligible_reject: int = 0
    eligible_delete: int = 0
    ineligible: int = 0
    items: List[BatchStatusPreviewItem] = []


@router.get("/batch-status", response_model=BatchStatusPreview, summary="批量操作预览")
async def preview_batch_status(
    voucher_ids: str = Query(..., description="逗号分隔的凭证ID列表"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """预览批量操作：统计符合条件与不符合条件的凭证数量"""
    try:
        ids = [int(x.strip()) for x in voucher_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="voucher_ids 格式错误，应为逗号分隔的整数")

    if not ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="voucher_ids 不能为空")

    result = BatchStatusPreview(total=len(ids))

    stmt = select(Voucher).where(Voucher.id.in_(ids))
    rows = await db.execute(stmt)
    vouchers = {v.id: v for v in rows.scalars().all()}

    for vid in ids:
        voucher = vouchers.get(vid)
        if voucher is None:
            item = BatchStatusPreviewItem(
                voucher_id=vid, voucher_no=f"ID:{vid}", current_status="不存在",
            )
            result.items.append(item)
            result.ineligible += 1
            continue

        item = BatchStatusPreviewItem(
            voucher_id=vid,
            voucher_no=voucher.voucher_no,
            current_status=voucher.status,
            can_submit=(voucher.status == "draft"),
            can_review=(voucher.status == "submitted"),
            can_approve=(voucher.status == "reviewed"),
            can_reject=(voucher.status == "submitted"),
            can_delete=(voucher.status == "draft"),
        )
        if item.can_submit:
            result.eligible_submit += 1
        if item.can_review:
            result.eligible_review += 1
        if item.can_approve:
            result.eligible_approve += 1
        if item.can_reject:
            result.eligible_reject += 1
        if item.can_delete:
            result.eligible_delete += 1

        if not (item.can_submit or item.can_review or item.can_approve or item.can_delete):
            result.ineligible += 1

        result.items.append(item)

    return result


@router.get("/{voucher_id}", response_model=VoucherResponse, summary="凭证详情")
async def get_voucher(
    voucher_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取凭证详细信息"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    user_role = current_user.role
    response_data = {
        "id": voucher.id,
        "voucher_type": voucher.voucher_type,
        "voucher_no": voucher.voucher_no,
        "voucher_date": voucher.voucher_date.isoformat(),
        "summary": voucher.summary,
        "status": voucher.status,
        "created_by": voucher.created_by,
        "reviewed_by": voucher.reviewed_by,
        "cashier_reviewed": voucher.cashier_reviewed,
        "cashier_reviewed_by": voucher.cashier_reviewed_by,
        "cashier_reviewed_at": voucher.cashier_reviewed_at.isoformat() if voucher.cashier_reviewed_at else None,
        "approved_by": voucher.approved_by,
        "approved_at": voucher.approved_at.isoformat() if voucher.approved_at else None,
        "posted_at": voucher.posted_at.isoformat() if voucher.posted_at else None,
        "created_at": voucher.created_at.isoformat() if voucher.created_at else None,
        "items": [
            {
                "id": i.id,
                "account_code": i.account_code,
                "account_name": i.account_name,
                "description": i.description,
                "debit_amount": float(i.debit_amount),
                "credit_amount": float(i.credit_amount),
            }
            for i in voucher.items
        ],
    }

    # 应用金额脱敏
    response_data = mask_voucher_response(response_data, user_role)

    return VoucherResponse(**response_data)


@router.put("/{voucher_id}", response_model=VoucherResponse, summary="更新凭证")
async def update_voucher(
    voucher_id: int,
    voucher_data: VoucherUpdate,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """更新凭证信息（仅 draft 状态）"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能修改草稿状态的凭证",
        )

    if voucher_data.voucher_type:
        voucher.voucher_type = voucher_data.voucher_type
    if voucher_data.voucher_date:
        voucher.voucher_date = date.fromisoformat(voucher_data.voucher_date)
    if voucher_data.summary:
        voucher.summary = voucher_data.summary

    if voucher_data.items is not None:
        # 校验借贷平衡
        total_debit = sum(item.debit_amount for item in voucher_data.items)
        total_credit = sum(item.credit_amount for item in voucher_data.items)
        if abs(total_debit - total_credit) > 0.01:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="借贷不平衡",
            )

        # 删除旧分录并添加新分录
        await db.execute(
            select(VoucherItem).where(VoucherItem.voucher_id == voucher.id)
        )
        # 直接删除旧记录
        for item in voucher.items:
            await db.delete(item)

        for item_data in voucher_data.items:
            item = VoucherItem(
                voucher_id=voucher.id,
                account_code=item_data.account_code,
                account_name=item_data.account_name,
                description=item_data.description,
                debit_amount=item_data.debit_amount,
                credit_amount=item_data.credit_amount,
            )
            db.add(item)

    await db.commit()
    await db.refresh(voucher)
    logger.info(f"用户 {current_user.username} 更新了凭证 {voucher.voucher_no}")

    return VoucherResponse(
        id=voucher.id,
        voucher_type=voucher.voucher_type,
        voucher_no=voucher.voucher_no,
        voucher_date=voucher.voucher_date.isoformat(),
        summary=voucher.summary,
        status=voucher.status,
        created_by=voucher.created_by,
        reviewed_by=voucher.reviewed_by,
        cashier_reviewed=voucher.cashier_reviewed,
        cashier_reviewed_by=voucher.cashier_reviewed_by,
        cashier_reviewed_at=voucher.cashier_reviewed_at.isoformat() if voucher.cashier_reviewed_at else None,
        approved_by=voucher.approved_by,
        approved_at=voucher.approved_at.isoformat() if voucher.approved_at else None,
        posted_at=voucher.posted_at.isoformat() if voucher.posted_at else None,
        created_at=voucher.created_at.isoformat() if voucher.created_at else None,
        items=[
            VoucherItemResponse(
                id=i.id,
                account_code=i.account_code,
                account_name=i.account_name,
                description=i.description,
                debit_amount=float(i.debit_amount),
                credit_amount=float(i.credit_amount),
                cash_flow_tag=i.cash_flow_tag,
                auxiliary_accounting=i.auxiliary_accounting,
            )
            for i in voucher.items
        ],
    )


@router.delete("/{voucher_id}", summary="删除凭证")
async def delete_voucher(
    voucher_id: int,
    current_user: User = Depends(require_permission("voucher:delete")),
    db: AsyncSession = Depends(get_db),
):
    """删除凭证（仅 draft 状态）"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能删除草稿状态的凭证",
        )

    await db.delete(voucher)
    await db.commit()
    logger.info(f"用户 {current_user.username} 删除了凭证 {voucher.voucher_no}")
    return {"message": "凭证已删除"}


@router.post("/{voucher_id}/submit", summary="提交审核")
async def submit_voucher(
    voucher_id: int,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """提交凭证进入审核流程"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能提交草稿状态的凭证",
        )

    voucher.status = "submitted"

    # 通知所有 reviewer 角色用户有凭证待审核
    from api.notification import create_notification
    reviewer_result = await db.execute(
        select(User).where(User.role.in_(["reviewer", "admin"]), User.is_active == True)
    )
    reviewers = reviewer_result.scalars().all()
    for reviewer in reviewers:
        await create_notification(
            db=db,
            user_id=reviewer.id,
            title="凭证待审核",
            content=f"用户 {current_user.real_name or current_user.username} 提交了凭证 {voucher.voucher_no}（摘要：{voucher.summary}），请及时审核。",
            book_id=voucher.book_id,
            notif_type="warning",
            category="voucher",
            link=f"/voucher/list?id={voucher.id}",
        )

    await db.commit()
    logger.info(f"用户 {current_user.username} 提交了凭证 {voucher.voucher_no} 审核")
    return {"message": "凭证已提交审核"}


@router.post("/{voucher_id}/review", summary="审核通过")
async def review_voucher(
    voucher_id: int,
    review_data: ReviewRequest,
    current_user: User = Depends(require_permission("voucher:review")),
    db: AsyncSession = Depends(get_db),
):
    """审核通过凭证"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能审核已提交状态的凭证",
        )

    voucher.status = "reviewed"
    voucher.reviewed_by = current_user.id

    # 通知凭证创建者凭证已审核通过
    from api.notification import create_notification
    if voucher.created_by != current_user.id:
        await create_notification(
            db=db,
            user_id=voucher.created_by,
            title="凭证已审核通过",
            content=f"您的凭证 {voucher.voucher_no}（摘要：{voucher.summary}）已被 {current_user.real_name or current_user.username} 审核通过。",
            book_id=voucher.book_id,
            notif_type="success",
            category="voucher",
            link=f"/voucher/list?id={voucher.id}",
        )

    await db.commit()
    logger.info(f"用户 {current_user.username} 审核通过了凭证 {voucher.voucher_no}")
    return {"message": "凭证审核通过"}


@router.post("/{voucher_id}/reject", summary="驳回凭证")
async def reject_voucher(
    voucher_id: int,
    review_data: ReviewRequest,
    current_user: User = Depends(require_permission("voucher:review")),
    db: AsyncSession = Depends(get_db),
):
    """驳回凭证到草稿状态"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能驳回已提交状态的凭证",
        )

    voucher.status = "draft"
    voucher.reviewed_by = current_user.id
    await db.commit()
    logger.info(
        f"用户 {current_user.username} 驳回了凭证 {voucher.voucher_no}"
        f"{'，原因: ' + review_data.comment if review_data.comment else ''}"
    )
    return {"message": "凭证已驳回"}


@router.post("/{voucher_id}/approve", summary="审批通过")
async def approve_voucher(
    voucher_id: int,
    review_data: ReviewRequest,
    current_user: User = Depends(require_permission("voucher:approve")),
    db: AsyncSession = Depends(get_db),
):
    """审批通过凭证（从 reviewed 到 approved）"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status != "reviewed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能审批已审核状态的凭证",
        )

    voucher.status = "approved"
    voucher.approved_by = current_user.id
    voucher.approved_at = datetime.now()
    await db.commit()
    logger.info(f"用户 {current_user.username} 审批通过了凭证 {voucher.voucher_no}")
    return {"message": "凭证审批通过"}


# ========== 出纳复核 ==========

CASH_BANK_ACCOUNTS = {"1001", "1002", "1012"}  # 现金/银行存款/其他货币资金


def _needs_cashier_review(voucher: Voucher) -> bool:
    """判断凭证是否需要出纳复核（涉及现金/银行科目）"""
    for item in voucher.items:
        if item.account_code in CASH_BANK_ACCOUNTS:
            return True
    return False


@router.post("/{voucher_id}/cashier-review", summary="出纳复核")
async def cashier_review_voucher(
    voucher_id: int,
    current_user: User = Depends(require_permission("voucher:cashier_review")),
    db: AsyncSession = Depends(get_db),
):
    """出纳复核凭证（涉及现金/银行科目的凭证需要出纳独立复核）"""
    # 检查系统设置：出纳复核是否启用
    from models.system_setting import SystemSetting
    setting_result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == "cashier_review_enabled")
    )
    setting = setting_result.scalar_one_or_none()
    if setting and setting.value != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="出纳复核功能已被管理员关闭",
        )

    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能复核已提交状态的凭证",
        )

    if not _needs_cashier_review(voucher):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该凭证不涉及现金/银行科目，无需出纳复核",
        )

    if voucher.created_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="制单人不能复核自己的凭证",
        )

    if voucher.cashier_reviewed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该凭证已完成出纳复核",
        )

    voucher.cashier_reviewed = True
    voucher.cashier_reviewed_by = current_user.id
    voucher.cashier_reviewed_at = datetime.now()

    await db.commit()
    logger.info(f"用户 {current_user.username} 对凭证 {voucher.voucher_no} 完成了出纳复核")
    return {"message": "出纳复核完成"}


@router.post("/{voucher_id}/cashier-unreview", summary="取消出纳复核")
async def cashier_unreview_voucher(
    voucher_id: int,
    current_user: User = Depends(require_permission("voucher:cashier_review")),
    db: AsyncSession = Depends(get_db),
):
    """取消出纳复核（仅已复核、未过账的凭证）"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status == "posted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已过账凭证不可取消出纳复核",
        )

    if not voucher.cashier_reviewed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该凭证未完成出纳复核",
        )

    voucher.cashier_reviewed = False
    voucher.cashier_reviewed_by = None
    voucher.cashier_reviewed_at = None

    await db.commit()
    logger.info(f"用户 {current_user.username} 取消了凭证 {voucher.voucher_no} 的出纳复核")
    return {"message": "出纳复核已取消"}


@router.post("/{voucher_id}/reject-to-draft", summary="驳回至草稿")
async def reject_to_draft(
    voucher_id: int,
    review_data: ReviewRequest,
    current_user: User = Depends(require_permission("voucher:review")),
    db: AsyncSession = Depends(get_db),
):
    """将凭证从任意非终态驳回至草稿状态"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    if voucher.status in ("draft", "posted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前状态 {voucher.status} 不允许驳回至草稿",
        )

    voucher.status = "draft"
    await db.commit()
    logger.info(
        f"用户 {current_user.username} 将凭证 {voucher.voucher_no} 驳回至草稿"
        f"{'，原因: ' + review_data.comment if review_data.comment else ''}"
    )
    return {"message": "凭证已驳回至草稿"}


@router.post("/ai-generate", summary="AI生成凭证")
async def ai_generate_voucher(
    ai_request: AiGenerateRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """使用 AI 根据自然语言描述生成记账凭证"""
    from services.voucher_ai_service import generate_voucher_by_ai

    try:
        voucher_data = await generate_voucher_by_ai(
            ai_request.description, current_user, db,
            voucher_date=ai_request.voucher_date,
            book_id=current_book.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return VoucherResponse(
        id=voucher_data["id"],
        voucher_type=voucher_data.get("voucher_type", "记"),
        voucher_no=voucher_data["voucher_no"],
        voucher_date=voucher_data["voucher_date"],
        summary=voucher_data["summary"],
        status=voucher_data["status"],
        created_by=voucher_data["created_by"],
        reviewed_by=voucher_data["reviewed_by"],
        cashier_reviewed=voucher_data.get("cashier_reviewed", False),
        cashier_reviewed_by=voucher_data.get("cashier_reviewed_by"),
        cashier_reviewed_at=voucher_data.get("cashier_reviewed_at"),
        approved_by=voucher_data.get("approved_by"),
        approved_at=voucher_data.get("approved_at"),
        posted_at=voucher_data["posted_at"],
        created_at=voucher_data["created_at"],
        items=[
            VoucherItemResponse(
                id=i["id"],
                account_code=i["account_code"],
                account_name=i["account_name"],
                description=i["description"],
                debit_amount=i["debit_amount"],
                credit_amount=i["credit_amount"],
            )
            for i in voucher_data["items"]
        ],
    )


# ========== 上传目录配置 ==========

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "voucher_attachments")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ========== 红字冲销 ==========

@router.post("/{voucher_id}/reverse", summary="红字冲销")
async def reverse_voucher(
    voucher_id: int,
    current_user: User = Depends(require_permission("voucher:create")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """创建红字冲销凭证（所有金额取反）"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    # 创建红字冲销凭证
    reverse_voucher = Voucher(
        voucher_type=voucher.voucher_type,
        voucher_no=await _generate_voucher_no(voucher.voucher_type, db),
        voucher_date=voucher.voucher_date,
        summary=f"【红字冲销】{voucher.summary}",
        status="draft",
        book_id=current_book.id,
        created_by=current_user.id,
    )
    db.add(reverse_voucher)
    await db.flush()

    # 所有金额取反
    for item in voucher.items:
        reverse_item = VoucherItem(
            voucher_id=reverse_voucher.id,
            account_code=item.account_code,
            account_name=item.account_name,
            description=item.description,
            debit_amount=-item.debit_amount,
            credit_amount=-item.credit_amount,
        )
        db.add(reverse_item)

    await db.commit()
    await db.refresh(reverse_voucher)
    logger.info(f"用户 {current_user.username} 对凭证 {voucher.voucher_no} 创建了红字冲销凭证 {reverse_voucher.voucher_no}")

    return VoucherResponse(
        id=reverse_voucher.id,
        voucher_no=reverse_voucher.voucher_no,
        voucher_date=reverse_voucher.voucher_date.isoformat(),
        summary=reverse_voucher.summary,
        status=reverse_voucher.status,
        created_by=reverse_voucher.created_by,
        reviewed_by=reverse_voucher.reviewed_by,
        posted_at=reverse_voucher.posted_at.isoformat() if reverse_voucher.posted_at else None,
        created_at=reverse_voucher.created_at.isoformat() if reverse_voucher.created_at else None,
        items=[
            VoucherItemResponse(
                id=i.id,
                account_code=i.account_code,
                account_name=i.account_name,
                description=i.description,
                debit_amount=float(i.debit_amount),
                credit_amount=float(i.credit_amount),
                cash_flow_tag=i.cash_flow_tag,
                auxiliary_accounting=i.auxiliary_accounting,
            )
            for i in reverse_voucher.items
        ],
    )


@router.post("/{voucher_id}/copy", summary="复制凭证")
async def copy_voucher(
    voucher_id: int,
    current_user: User = Depends(require_permission("voucher:create")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """复制凭证为草稿状态（生成新凭证号）"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    copied = Voucher(
        voucher_type=voucher.voucher_type,
        voucher_no=await _generate_voucher_no(voucher.voucher_type, db),
        voucher_date=voucher.voucher_date,
        summary=f"【复制】{voucher.summary}",
        status="draft",
        book_id=current_book.id,
        created_by=current_user.id,
    )
    db.add(copied)
    await db.flush()

    for item in voucher.items:
        copied_item = VoucherItem(
            voucher_id=copied.id,
            account_code=item.account_code,
            account_name=item.account_name,
            description=item.description,
            debit_amount=item.debit_amount,
            credit_amount=item.credit_amount,
            cash_flow_tag=item.cash_flow_tag,
            auxiliary_accounting=item.auxiliary_accounting,
        )
        db.add(copied_item)

    await db.commit()
    await db.refresh(copied)
    logger.info(f"用户 {current_user.username} 复制了凭证 {voucher.voucher_no} → {copied.voucher_no}")

    return VoucherResponse(
        id=copied.id,
        voucher_no=copied.voucher_no,
        voucher_date=copied.voucher_date.isoformat(),
        summary=copied.summary,
        status=copied.status,
        created_by=copied.created_by,
        reviewed_by=copied.reviewed_by,
        voucher_type=copied.voucher_type,
        posted_at=None,
        created_at=copied.created_at.isoformat() if copied.created_at else None,
        items=[
            VoucherItemResponse(
                id=i.id,
                account_code=i.account_code,
                account_name=i.account_name,
                description=i.description,
                debit_amount=float(i.debit_amount),
                credit_amount=float(i.credit_amount),
                cash_flow_tag=i.cash_flow_tag,
                auxiliary_accounting=i.auxiliary_accounting,
            )
            for i in copied.items
        ],
    )


# ========== 附件管理 ==========

@router.post("/{voucher_id}/attachments", summary="上传附件")
async def upload_attachments(
    voucher_id: int,
    files: List[UploadFile] = File(..., description="附件文件"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传凭证附件（支持图片、PDF）"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    # 创建凭证附件目录
    voucher_dir = os.path.join(UPLOAD_DIR, str(voucher_id))
    os.makedirs(voucher_dir, exist_ok=True)

    # 获取现有附件列表
    existing_attachments = voucher.attachments or []
    if isinstance(existing_attachments, dict):
        existing_attachments = [existing_attachments]

    uploaded = []
    for file in files:
        # 安全检查：防止路径遍历
        safe_filename = os.path.basename(file.filename)
        file_path = os.path.join(voucher_dir, safe_filename)

        # 保存文件
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        file_size = len(content)
        attachment_entry = {
            "filename": safe_filename,
            "path": file_path,
            "size": file_size,
            "uploaded_at": datetime.now().isoformat(),
        }
        existing_attachments.append(attachment_entry)
        uploaded.append(attachment_entry)

    voucher.attachments = existing_attachments
    await db.commit()
    logger.info(f"用户 {current_user.username} 为凭证 {voucher.voucher_no} 上传了 {len(uploaded)} 个附件")

    return {"attachments": existing_attachments}


@router.get("/{voucher_id}/attachments", summary="获取附件列表")
async def get_attachments(
    voucher_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取凭证附件列表"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    attachments = voucher.attachments or []
    return {"attachments": attachments}


@router.get("/{voucher_id}/attachments/{filename}", summary="下载附件")
async def download_attachment(
    voucher_id: int,
    filename: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """下载凭证附件"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    attachments = voucher.attachments or []
    attachment = None
    for att in attachments:
        if att.get("filename") == filename:
            attachment = att
            break

    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    file_path = attachment.get("path", "")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件文件不存在")

    return FileResponse(file_path, filename=filename)


@router.delete("/{voucher_id}/attachments/{filename}", summary="删除附件")
async def delete_attachment(
    voucher_id: int,
    filename: str,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """删除凭证附件"""
    result = await db.execute(
        select(Voucher).where(Voucher.id == voucher_id)
    )
    voucher = result.scalar_one_or_none()
    if voucher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="凭证不存在")

    attachments = voucher.attachments or []
    found = None
    new_attachments = []
    for att in attachments:
        if att.get("filename") == filename:
            found = att
        else:
            new_attachments.append(att)

    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在")

    # 删除物理文件
    file_path = found.get("path", "")
    if os.path.exists(file_path):
        os.remove(file_path)

    voucher.attachments = new_attachments if new_attachments else None
    await db.commit()
    logger.info(f"用户 {current_user.username} 删除了凭证 {voucher.voucher_no} 的附件 {filename}")

    return {"message": "附件已删除", "attachments": new_attachments}


# ========== 批量操作 ==========

VALID_STATUS_TRANSITIONS = {
    "draft": {"submitted"},
    "submitted": {"reviewed", "draft"},
    "reviewed": {"approved", "draft"},
    "approved": {"posted", "draft"},
    "posted": set(),
}


@router.post("/batch-submit", response_model=BatchResult, summary="批量提交审核")
async def batch_submit_vouchers(
    batch_data: BatchRequest,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """批量提交凭证进入审核流程（仅草稿状态）"""
    result = BatchResult()
    for voucher_id in batch_data.voucher_ids:
        try:
            stmt = select(Voucher).where(Voucher.id == voucher_id)
            row = await db.execute(stmt)
            voucher = row.scalar_one_or_none()
            if voucher is None:
                result.results.append(BatchResultItem(id=voucher_id, status="failed", error="凭证不存在"))
                result.failed_count += 1
                continue
            if voucher.status != "draft":
                result.results.append(BatchResultItem(
                    id=voucher_id, status="failed",
                    error=f"只能提交草稿状态的凭证，当前状态: {voucher.status}",
                ))
                result.failed_count += 1
                continue
            voucher.status = "submitted"
            result.results.append(BatchResultItem(id=voucher_id, status="success"))
            result.success_count += 1
        except Exception as e:
            result.results.append(BatchResultItem(id=voucher_id, status="failed", error=str(e)))
            result.failed_count += 1

    await db.commit()
    logger.info(
        f"用户 {current_user.username} 批量提交审核: "
        f"成功 {result.success_count}, 失败 {result.failed_count}"
    )
    return result


@router.post("/batch-review", response_model=BatchResult, summary="批量审核通过")
async def batch_review_vouchers(
    batch_data: BatchRequest,
    current_user: User = Depends(require_permission("voucher:review")),
    db: AsyncSession = Depends(get_db),
):
    """批量审核通过凭证（仅已提交状态）"""
    result = BatchResult()
    for voucher_id in batch_data.voucher_ids:
        try:
            stmt = select(Voucher).where(Voucher.id == voucher_id)
            row = await db.execute(stmt)
            voucher = row.scalar_one_or_none()
            if voucher is None:
                result.results.append(BatchResultItem(id=voucher_id, status="failed", error="凭证不存在"))
                result.failed_count += 1
                continue
            if voucher.status != "submitted":
                result.results.append(BatchResultItem(
                    id=voucher_id, status="failed",
                    error=f"只能审核已提交状态的凭证，当前状态: {voucher.status}",
                ))
                result.failed_count += 1
                continue
            voucher.status = "reviewed"
            voucher.reviewed_by = current_user.id
            result.results.append(BatchResultItem(id=voucher_id, status="success"))
            result.success_count += 1
        except Exception as e:
            result.results.append(BatchResultItem(id=voucher_id, status="failed", error=str(e)))
            result.failed_count += 1

    await db.commit()
    logger.info(
        f"用户 {current_user.username} 批量审核通过: "
        f"成功 {result.success_count}, 失败 {result.failed_count}"
    )
    return result


@router.post("/batch-reject", response_model=BatchResult, summary="批量驳回")
async def batch_reject_vouchers(
    batch_data: BatchRequest,
    current_user: User = Depends(require_permission("voucher:review")),
    db: AsyncSession = Depends(get_db),
):
    """批量驳回凭证到草稿状态"""
    result = BatchResult()
    for voucher_id in batch_data.voucher_ids:
        try:
            stmt = select(Voucher).where(Voucher.id == voucher_id)
            row = await db.execute(stmt)
            voucher = row.scalar_one_or_none()
            if voucher is None:
                result.results.append(BatchResultItem(id=voucher_id, status="failed", error="凭证不存在"))
                result.failed_count += 1
                continue
            if voucher.status != "submitted":
                result.results.append(BatchResultItem(
                    id=voucher_id, status="failed",
                    error=f"只能驳回已提交状态的凭证，当前状态: {voucher.status}",
                ))
                result.failed_count += 1
                continue
            voucher.status = "draft"
            voucher.reviewed_by = current_user.id
            result.results.append(BatchResultItem(id=voucher_id, status="success"))
            result.success_count += 1
        except Exception as e:
            result.results.append(BatchResultItem(id=voucher_id, status="failed", error=str(e)))
            result.failed_count += 1

    await db.commit()
    logger.info(
        f"用户 {current_user.username} 批量驳回: "
        f"成功 {result.success_count}, 失败 {result.failed_count}"
    )
    return result


@router.post("/batch-approve", response_model=BatchResult, summary="批量审批通过")
async def batch_approve_vouchers(
    batch_data: BatchRequest,
    current_user: User = Depends(require_permission("voucher:approve")),
    db: AsyncSession = Depends(get_db),
):
    """批量审批通过凭证（仅已审核状态）"""
    result = BatchResult()
    for voucher_id in batch_data.voucher_ids:
        try:
            stmt = select(Voucher).where(Voucher.id == voucher_id)
            row = await db.execute(stmt)
            voucher = row.scalar_one_or_none()
            if voucher is None:
                result.results.append(BatchResultItem(id=voucher_id, status="failed", error="凭证不存在"))
                result.failed_count += 1
                continue
            if voucher.status != "reviewed":
                result.results.append(BatchResultItem(
                    id=voucher_id, status="failed",
                    error=f"只能审批已审核状态的凭证，当前状态: {voucher.status}",
                ))
                result.failed_count += 1
                continue
            voucher.status = "approved"
            voucher.approved_by = current_user.id
            voucher.approved_at = datetime.now()
            result.results.append(BatchResultItem(id=voucher_id, status="success"))
            result.success_count += 1
        except Exception as e:
            result.results.append(BatchResultItem(id=voucher_id, status="failed", error=str(e)))
            result.failed_count += 1

    await db.commit()
    logger.info(
        f"用户 {current_user.username} 批量审批通过: "
        f"成功 {result.success_count}, 失败 {result.failed_count}"
    )
    return result


@router.post("/batch-delete", response_model=BatchResult, summary="批量删除")
async def batch_delete_vouchers(
    batch_data: BatchRequest,
    current_user: User = Depends(require_permission("voucher:delete")),
    db: AsyncSession = Depends(get_db),
):
    """批量删除凭证（仅草稿状态）"""
    result = BatchResult()
    for voucher_id in batch_data.voucher_ids:
        try:
            stmt = select(Voucher).where(Voucher.id == voucher_id)
            row = await db.execute(stmt)
            voucher = row.scalar_one_or_none()
            if voucher is None:
                result.results.append(BatchResultItem(id=voucher_id, status="failed", error="凭证不存在"))
                result.failed_count += 1
                continue
            if voucher.status != "draft":
                result.results.append(BatchResultItem(
                    id=voucher_id, status="failed",
                    error=f"只能删除草稿状态的凭证，当前状态: {voucher.status}",
                ))
                result.failed_count += 1
                continue
            await db.delete(voucher)
            result.results.append(BatchResultItem(id=voucher_id, status="success"))
            result.success_count += 1
        except Exception as e:
            result.results.append(BatchResultItem(id=voucher_id, status="failed", error=str(e)))
            result.failed_count += 1

    await db.commit()
    logger.info(
        f"用户 {current_user.username} 批量删除: "
        f"成功 {result.success_count}, 失败 {result.failed_count}"
    )
    return result


@router.post("/batch-post", response_model=BatchResult, summary="批量过账")
async def batch_post_vouchers(
    batch_data: BatchRequest,
    current_user: User = Depends(require_permission("voucher:approve")),
    db: AsyncSession = Depends(get_db),
):
    """批量过账凭证（仅已审批状态）"""
    result = BatchResult()
    for voucher_id in batch_data.voucher_ids:
        try:
            stmt = select(Voucher).where(Voucher.id == voucher_id)
            row = await db.execute(stmt)
            voucher = row.scalar_one_or_none()
            if voucher is None:
                result.results.append(BatchResultItem(id=voucher_id, status="failed", error="凭证不存在"))
                result.failed_count += 1
                continue
            if voucher.status != "approved":
                result.results.append(BatchResultItem(
                    id=voucher_id, status="failed",
                    error=f"只能过账已审批状态的凭证，当前状态: {voucher.status}",
                ))
                result.failed_count += 1
                continue
            voucher.status = "posted"
            voucher.posted_at = datetime.now()
            result.results.append(BatchResultItem(id=voucher_id, status="success"))
            result.success_count += 1
        except Exception as e:
            result.results.append(BatchResultItem(id=voucher_id, status="failed", error=str(e)))
            result.failed_count += 1

    await db.commit()
    logger.info(
        f"用户 {current_user.username} 批量过账: "
        f"成功 {result.success_count}, 失败 {result.failed_count}"
    )
    return result


@router.post("/batch-export", summary="批量导出选中凭证")
async def batch_export_vouchers(
    batch_data: BatchRequest,
    current_user: User = Depends(require_permission("report:export")),
    db: AsyncSession = Depends(get_db),
):
    """批量导出选中凭证为 Excel 文件"""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from fastapi.responses import Response

    # 查询选中的凭证
    stmt = (
        select(Voucher)
        .where(Voucher.id.in_(batch_data.voucher_ids))
        .order_by(Voucher.voucher_date.desc(), Voucher.id.desc())
    )
    row = await db.execute(stmt)
    vouchers = row.scalars().all()

    if not vouchers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到任何凭证")

    wb = Workbook()
    ws = wb.active
    ws.title = "凭证导出"

    # 样式定义
    header_font = Font(name="微软雅黑", bold=True, size=11, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    data_font = Font(name="微软雅黑", size=10)
    data_align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    data_align_right = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    def _style_header(ws, row, col, value, width=None):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border
        if width:
            ws.column_dimensions[cell.column_letter].width = width

    def _style_cell(ws, row, col, value, is_number=False):
        cell = ws.cell(row=row, column=col, value=value)
        cell.font = data_font
        cell.alignment = data_align_right if is_number else data_align_left
        cell.border = thin_border
        if is_number:
            cell.number_format = "#,##0.00"

    # 表头
    headers = [
        ("凭证号", 20), ("凭证日期", 15), ("摘要", 40), ("状态", 12),
        ("科目编码", 15), ("科目名称", 20), ("分录描述", 30),
        ("借方金额", 15), ("贷方金额", 15),
    ]
    for i, (h, w) in enumerate(headers, start=1):
        _style_header(ws, 1, i, h, w)

    status_labels = {"draft": "草稿", "submitted": "已提交", "reviewed": "已审核", "approved": "已审批", "posted": "已过账"}
    row_num = 2
    for voucher in vouchers:
        status_label = status_labels.get(voucher.status, voucher.status)
        vd = voucher.voucher_date.isoformat() if voucher.voucher_date else ""
        items = voucher.items if voucher.items else []
        if not items:
            _style_cell(ws, row_num, 1, voucher.voucher_no)
            _style_cell(ws, row_num, 2, vd)
            _style_cell(ws, row_num, 3, voucher.summary)
            _style_cell(ws, row_num, 4, status_label)
            for c in range(5, 10):
                _style_cell(ws, row_num, c, "")
            row_num += 1
        else:
            first = True
            for item in items:
                if first:
                    _style_cell(ws, row_num, 1, voucher.voucher_no)
                    _style_cell(ws, row_num, 2, vd)
                    _style_cell(ws, row_num, 3, voucher.summary)
                    _style_cell(ws, row_num, 4, status_label)
                    first = False
                else:
                    for c in range(1, 5):
                        _style_cell(ws, row_num, c, "")
                _style_cell(ws, row_num, 5, item.account_code)
                _style_cell(ws, row_num, 6, item.account_name)
                _style_cell(ws, row_num, 7, item.description)
                _style_cell(ws, row_num, 8, float(item.debit_amount), is_number=True)
                _style_cell(ws, row_num, 9, float(item.credit_amount), is_number=True)
                row_num += 1

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"vouchers_batch_export.xlsx"
    logger.info(f"用户 {current_user.username} 批量导出了 {len(vouchers)} 条凭证")
    return Response(
        content=output.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/batch-status", response_model=BatchResult, summary="批量更新状态")
async def batch_update_status(
    batch_data: BatchStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量更新凭证状态，自动校验状态转换合法性"""
    target = batch_data.target_status
    if target not in VALID_STATUS_TRANSITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的目标状态: {target}，有效状态: {list(VALID_STATUS_TRANSITIONS.keys())}",
        )

    result = BatchResult()
    for voucher_id in batch_data.voucher_ids:
        try:
            stmt = select(Voucher).where(Voucher.id == voucher_id)
            row = await db.execute(stmt)
            voucher = row.scalar_one_or_none()
            if voucher is None:
                result.results.append(BatchResultItem(id=voucher_id, status="failed", error="凭证不存在"))
                result.failed_count += 1
                continue

            current_status = voucher.status
            allowed = VALID_STATUS_TRANSITIONS.get(current_status, set())
            if target not in allowed:
                result.results.append(BatchResultItem(
                    id=voucher_id, status="failed",
                    error=f"不允许从 {current_status} 转换到 {target}",
                ))
                result.failed_count += 1
                continue

            voucher.status = target
            if target == "reviewed":
                voucher.reviewed_by = current_user.id
            if target == "approved":
                voucher.approved_by = current_user.id
                voucher.approved_at = datetime.now()
            result.results.append(BatchResultItem(id=voucher_id, status="success"))
            result.success_count += 1
        except Exception as e:
            result.results.append(BatchResultItem(id=voucher_id, status="failed", error=str(e)))
            result.failed_count += 1

    await db.commit()
    logger.info(
        f"用户 {current_user.username} 批量更新状态到 {target}: "
        f"成功 {result.success_count}, 失败 {result.failed_count}"
    )
    return result


# ========== 期末结转 ==========

class CarryForwardRequest(BaseModel):
    """期末结转请求"""
    period_end_date: str = Field(..., description="期末日期 YYYY-MM-DD")
    carry_types: list[str] = Field(
        default=["损益结转"],
        description="结转类型: 损益结转, 成本结转"
    )


class CarryForwardResult(BaseModel):
    """结转结果"""
    carry_type: str
    voucher_id: int | None = None
    voucher_no: str | None = None
    entry_count: int = 0
    total_amount: float = 0
    message: str


@router.post("/period-close/carry-forward", summary="期末结转")
async def period_carry_forward(
    req: CarryForwardRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """
    自动生成期末结转凭证
    支持损益结转和成本结转
    """
    book_id = current_book.id

    results: list[CarryForwardResult] = []

    # 获取相关科目
    acc_result = await db.execute(
        select(Account).where(Account.book_id == book_id)
    )
    accounts = {a.account_code: a for a in acc_result.scalars().all()}

    if not accounts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前账套无科目数据")

    # 本年利润科目
    profit_account = accounts.get("4103")
    if not profit_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未找到本年利润科目(4103)，请先初始化科目",
        )

    for carry_type in req.carry_types:
        if carry_type == "损益结转":
            result = await _carry_forward_profit_loss(
                db, book_id, accounts, profit_account,
                req.period_end_date, current_user.id,
            )
            results.append(result)
        elif carry_type == "成本结转":
            result = await _carry_forward_cost(
                db, book_id, accounts, profit_account,
                req.period_end_date, current_user.id,
            )
            results.append(result)

    return {"results": [r.model_dump() for r in results]}


async def _carry_forward_profit_loss(
    db: AsyncSession,
    book_id: int,
    accounts: dict,
    profit_account: Account,
    end_date: str,
    user_id: int,
) -> CarryForwardResult:
    """损益结转：将损益类科目余额结转到本年利润"""
    items = []

    # 获取所有损益类科目
    pl_accounts = [a for a in accounts.values() if a.account_type in ("revenue", "expense")]
    if not pl_accounts:
        return CarryForwardResult(
            carry_type="损益结转",
            message="无损益类科目",
        )

    for acc in pl_accounts:
        # 计算该科目在期间内的余额
        balance = await _calculate_account_balance(db, book_id, acc.account_code, end_date)
        if abs(balance) < 0.01:
            continue

        entry = _build_carry_forward_entry(acc, balance, profit_account)
        if entry:
            items.append(entry)

    if not items:
        return CarryForwardResult(
            carry_type="损益结转",
            message="损益类科目余额均已为零，无需结转",
        )

    # 创建结转凭证
    voucher = await _create_carry_forward_voucher(
        db, book_id, user_id, end_date, "期末损益结转", items,
    )
    total_amount = float(sum(
        i.get("debit_amount", i.get("credit_amount", 0)) for i in items
    )) / 2  # 借贷各半

    return CarryForwardResult(
        carry_type="损益结转",
        voucher_id=voucher.id,
        voucher_no=voucher.voucher_no,
        entry_count=len(items),
        total_amount=total_amount,
        message=f"损益结转完成，生成凭证 {voucher.voucher_no}",
    )


async def _carry_forward_cost(
    db: AsyncSession,
    book_id: int,
    accounts: dict,
    profit_account: Account,
    end_date: str,
    user_id: int,
) -> CarryForwardResult:
    """成本结转：将成本类科目余额结转到本年利润"""
    items = []

    cost_accounts = [a for a in accounts.values() if a.account_type == "cost"]
    if not cost_accounts:
        return CarryForwardResult(
            carry_type="成本结转",
            message="无成本类科目",
        )

    for acc in cost_accounts:
        balance = await _calculate_account_balance(db, book_id, acc.account_code, end_date)
        if abs(balance) < 0.01:
            continue

        entry = _build_carry_forward_entry(acc, balance, profit_account)
        if entry:
            items.append(entry)

    if not items:
        return CarryForwardResult(
            carry_type="成本结转",
            message="成本类科目余额均已为零，无需结转",
        )

    voucher = await _create_carry_forward_voucher(
        db, book_id, user_id, end_date, "期末成本结转", items,
    )
    total_amount = float(sum(
        i.get("debit_amount", i.get("credit_amount", 0)) for i in items
    )) / 2

    return CarryForwardResult(
        carry_type="成本结转",
        voucher_id=voucher.id,
        voucher_no=voucher.voucher_no,
        entry_count=len(items),
        total_amount=total_amount,
        message=f"成本结转完成，生成凭证 {voucher.voucher_no}",
    )


async def _calculate_account_balance(
    db: AsyncSession,
    book_id: int,
    account_code: str,
    end_date: str,
) -> float:
    """计算指定科目在指定日期之前的余额"""
    from sqlalchemy import select, func as sql_func

    # 查询该科目所有分录
    result = await db.execute(
        select(
            sql_func.coalesce(sql_func.sum(VoucherItem.debit_amount), 0),
            sql_func.coalesce(sql_func.sum(VoucherItem.credit_amount), 0),
        )
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            VoucherItem.account_code == account_code,
            Voucher.book_id == book_id,
            Voucher.voucher_date <= date.fromisoformat(end_date),
            Voucher.status.in_(["reviewed", "approved", "posted"]),
        )
    )
    total_debit, total_credit = result.one()
    return float(total_debit) - float(total_credit)


def _build_carry_forward_entry(
    acc: Account,
    balance: float,
    profit_account: Account,
) -> dict | None:
    """
    构建结转分录
    收入类科目(credit方向有余额): 借收入科目, 贷本年利润
    费用/成本类科目(debit方向有余额): 借本年利润, 贷费用科目
    """
    if acc.balance_direction == "credit":
        # 收入类科目，贷方余额 → 借方转出到本年利润贷方
        return {
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "description": f"结转{acc.account_name}",
            "debit_amount": round(abs(balance), 2),
            "credit_amount": 0,
            "counter_account_code": profit_account.account_code,
            "counter_account_name": profit_account.account_name,
            "counter_debit_amount": 0,
            "counter_credit_amount": round(abs(balance), 2),
        }
    else:
        # 费用/成本类科目，借方余额 → 贷方转出到本年利润借方
        return {
            "account_code": acc.account_code,
            "account_name": acc.account_name,
            "description": f"结转{acc.account_name}",
            "debit_amount": 0,
            "credit_amount": round(abs(balance), 2),
            "counter_account_code": profit_account.account_code,
            "counter_account_name": profit_account.account_name,
            "counter_debit_amount": round(abs(balance), 2),
            "counter_credit_amount": 0,
        }


async def _create_carry_forward_voucher(
    db: AsyncSession,
    book_id: int,
    user_id: int,
    end_date: str,
    summary: str,
    items: list[dict],
) -> Voucher:
    """创建结转凭证"""
    from collections import defaultdict

    # 汇总本年利润科目的分录
    profit_entries: dict[str, float] = defaultdict(float)
    regular_entries = []

    for item in items:
        regular_entries.append(item)
        profit_entries["debit"] += item.get("counter_debit_amount", 0)
        profit_entries["credit"] += item.get("counter_credit_amount", 0)

    voucher = Voucher(
        voucher_type="记",
        voucher_no=await _generate_voucher_no("记", db),
        voucher_date=date.fromisoformat(end_date),
        summary=summary,
        status="draft",
        book_id=book_id,
        created_by=user_id,
    )
    db.add(voucher)
    await db.flush()

    # 添加各科目结转分录
    for item in regular_entries:
        db.add(VoucherItem(
            voucher_id=voucher.id,
            account_code=item["account_code"],
            account_name=item["account_name"],
            description=item["description"],
            debit_amount=item["debit_amount"],
            credit_amount=item["credit_amount"],
        ))

    # 添加本年利润汇总分录
    db.add(VoucherItem(
        voucher_id=voucher.id,
        account_code=items[0]["counter_account_code"],
        account_name=items[0]["counter_account_name"],
        description=f"{summary}",
        debit_amount=round(profit_entries["debit"], 2),
        credit_amount=round(profit_entries["credit"], 2),
    ))

    await db.commit()
    await db.refresh(voucher)
    return voucher


# ========== PDF导出 ==========

@router.get("/{voucher_id}/export-pdf", summary="导出凭证PDF")
async def export_voucher_pdf(
    voucher_id: int,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """导出单个凭证为PDF文件"""
    result = await db.execute(
        select(Voucher).where(
            Voucher.id == voucher_id,
            Voucher.book_id == current_book.id,
        )
    )
    voucher = result.scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=404, detail="凭证不存在")

    await db.refresh(voucher, ["items"])

    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()

        # 加载中文字体
        font_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        font_path = os.path.join(font_dir, "SimSun.ttf")
        if not os.path.exists(font_path):
            # 尝试系统字体路径
            system_fonts = [
                "C:/Windows/Fonts/simsun.ttc",
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simhei.ttf",
            ]
            for sf in system_fonts:
                if os.path.exists(sf):
                    font_path = sf
                    break
            else:
                raise HTTPException(status_code=500, detail="未找到中文字体文件")

        pdf.add_font("CJK", "", font_path, uni=True)
        pdf.add_font("CJK", "B", font_path, uni=True)
        pdf.set_font("CJK", "B", 16)

        # 标题
        pdf.cell(0, 10, "记账凭证", new_x="LMARGIN", new_y="NEXT", align="C")
        pdf.ln(4)

        # 基本信息
        pdf.set_font("CJK", "", 10)
        info_lines = [
            f"凭证字: {voucher.voucher_type}          凭证号: {voucher.voucher_no}",
            f"日期: {voucher.voucher_date}          摘要: {voucher.summary}",
            f"状态: {voucher.status}",
        ]
        for line in info_lines:
            pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # 表头
        pdf.set_font("CJK", "B", 9)
        col_widths = [18, 28, 40, 30, 28, 28, 28]
        headers = ["序号", "科目代码", "科目名称", "摘要", "借方金额", "贷方金额", "现金流"]
        for i, (header, w) in enumerate(zip(headers, col_widths)):
            pdf.cell(w, 8, header, border=1, align="C")
        pdf.ln()

        # 表体
        pdf.set_font("CJK", "", 9)
        total_debit = 0
        total_credit = 0
        for idx, item in enumerate(voucher.items, 1):
            row_data = [
                str(idx),
                item.account_code,
                item.account_name,
                item.description[:12] if item.description else "",
                f"{float(item.debit_amount):.2f}" if float(item.debit_amount) > 0 else "",
                f"{float(item.credit_amount):.2f}" if float(item.credit_amount) > 0 else "",
                _cash_flow_label(item.cash_flow_tag) if item.cash_flow_tag else "",
            ]
            total_debit += float(item.debit_amount)
            total_credit += float(item.credit_amount)
            for i, (data, w) in enumerate(zip(row_data, col_widths)):
                align = "R" if i >= 4 else "L"
                pdf.cell(w, 7, data, border=1, align=align)
            pdf.ln()

        # 合计行
        pdf.set_font("CJK", "B", 9)
        total_data = ["", "", "", "合计", f"{total_debit:.2f}", f"{total_credit:.2f}", ""]
        for data, w in zip(total_data, col_widths):
            align = "R" if data and data != "合计" else "L"
            pdf.cell(w, 7, data, border=1, align=align)
        pdf.ln(8)

        # 签名区
        pdf.set_font("CJK", "", 9)
        pdf.cell(45, 8, f"制单人: {current_user.username}", new_x="RIGHT", new_y="LAST")
        pdf.cell(45, 8, "审核人: ", new_x="RIGHT", new_y="LAST")
        pdf.cell(45, 8, "出纳: ", new_x="RIGHT", new_y="LAST")
        pdf.cell(45, 8, "记账人: ", new_x="LMARGIN", new_y="NEXT")

        # 保存临时文件
        temp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        pdf_path = os.path.join(temp_dir, f"voucher_{voucher_id}_{voucher.voucher_no}.pdf")
        pdf.output(pdf_path)

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"凭证_{voucher.voucher_no}.pdf",
            background=lambda: os.remove(pdf_path) if os.path.exists(pdf_path) else None,
        )

    except ImportError:
        raise HTTPException(status_code=500, detail="PDF导出功能未安装，请安装 fpdf2 库")
    except Exception as e:
        logger.error(f"PDF导出失败: {e}")
        raise HTTPException(status_code=500, detail=f"PDF导出失败: {str(e)}")


def _cash_flow_label(tag: str) -> str:
    labels = {"operating": "经营", "investing": "投资", "financing": "筹资"}
    return labels.get(tag, tag)


# ========== 断号整理 ==========

class GapInfo(BaseModel):
    """断号信息"""
    voucher_type: str
    gap_start: str
    gap_end: str
    missing_count: int
    missing_numbers: list[str]


class GapDetectionResponse(BaseModel):
    """断号检测响应"""
    has_gaps: bool
    gaps: list[GapInfo]
    total_missing: int


class RenumberRequest(BaseModel):
    """重新编号请求"""
    voucher_type: Optional[str] = Field(None, description="指定凭证字，不指定则整理全部")
    start_date: Optional[str] = Field(None, description="从指定日期开始整理")


@router.get("/gaps/detect", response_model=GapDetectionResponse, summary="断号检测")
async def detect_voucher_gaps(
    voucher_type: Optional[str] = Query(None, description="凭证字筛选"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """检测凭证编号中的断号"""
    book_id = current_book.id

    # 按凭证字分组查询所有凭证号
    query = select(Voucher.voucher_type, Voucher.voucher_no).where(
        Voucher.book_id == book_id
    )
    if voucher_type:
        query = query.where(Voucher.voucher_type == voucher_type)
    query = query.order_by(Voucher.voucher_type, Voucher.voucher_no)

    result = await db.execute(query)
    all_vouchers = result.all()

    # 按凭证字分组
    type_groups: dict[str, list[str]] = {}
    for vt, vn in all_vouchers:
        type_groups.setdefault(vt, []).append(vn)

    gaps = []
    total_missing = 0

    for vt, numbers in type_groups.items():
        # 提取凭证号中的序号（格式: 记-2026-08-001）
        parsed = []
        for n in numbers:
            parts = n.rsplit("-", 1)
            if len(parts) == 2:
                try:
                    seq = int(parts[1])
                    parsed.append((n, seq, parts[0]))
                except ValueError:
                    continue

        if not parsed:
            continue

        parsed.sort(key=lambda x: x[1])
        min_seq = parsed[0][1]
        max_seq = parsed[-1][1]
        existing_seqs = {p[1] for p in parsed}

        # 找出缺失的序号
        missing = []
        for seq in range(min_seq, max_seq + 1):
            if seq not in existing_seqs:
                prefix = parsed[0][2]
                missing.append(f"{prefix}-{seq:03d}")

        if missing:
            gaps.append(GapInfo(
                voucher_type=vt,
                gap_start=missing[0],
                gap_end=missing[-1],
                missing_count=len(missing),
                missing_numbers=missing,
            ))
            total_missing += len(missing)

    return GapDetectionResponse(
        has_gaps=len(gaps) > 0,
        gaps=gaps,
        total_missing=total_missing,
    )


@router.post("/gaps/renumber", summary="断号整理/重新编号")
async def renumber_vouchers(
    req: RenumberRequest,
    current_user: User = Depends(require_permission("voucher:update")),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """重新整理凭证编号，消除断号"""
    book_id = current_book.id

    # 查询需要整理的凭证
    query = select(Voucher).where(
        Voucher.book_id == book_id,
        Voucher.status.in_(["draft", "submitted", "cashier_reviewed", "reviewed", "approved", "posted"]),
    )
    if req.voucher_type:
        query = query.where(Voucher.voucher_type == req.voucher_type)
    if req.start_date:
        query = query.where(Voucher.voucher_date >= date.fromisoformat(req.start_date))

    query = query.order_by(Voucher.voucher_type, Voucher.voucher_date, Voucher.voucher_no)
    result = await db.execute(query)
    vouchers = result.scalars().all()

    if not vouchers:
        return {"message": "没有需要整理的凭证", "renumbered": 0}

    # 按凭证字分组重新编号
    type_groups: dict[str, list[Voucher]] = {}
    for v in vouchers:
        type_groups.setdefault(v.voucher_type, []).append(v)

    renumbered = 0
    for vt, v_list in type_groups.items():
        for idx, v in enumerate(v_list, 1):
            # 提取年份月份前缀
            year_month = v.voucher_date.strftime("%Y-%m") if v.voucher_date else "0000-00"
            new_no = f"{vt}-{year_month}-{idx:03d}"
            if v.voucher_no != new_no:
                v.voucher_no = new_no
                renumbered += 1

    await db.commit()
    logger.info(f"断号整理完成，重新编号 {renumbered} 条凭证")
    return {"message": f"断号整理完成，重新编号 {renumbered} 条凭证", "renumbered": renumbered}


# ========== 现金流量标记 ==========

class CashFlowUpdateRequest(BaseModel):
    """现金流量标记更新请求"""
    item_id: int = Field(..., description="分录ID")
    cash_flow_tag: Optional[str] = Field(None, description="现金流量标记: operating/investing/financing")


@router.put("/items/{item_id}/cash-flow", summary="更新现金流量标记")
async def update_cash_flow_tag(
    item_id: int,
    req: CashFlowUpdateRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """更新凭证分录的现金流量标记"""
    result = await db.execute(
        select(VoucherItem).join(Voucher).where(
            VoucherItem.id == item_id,
            Voucher.book_id == current_book.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="分录不存在")

    item.cash_flow_tag = req.cash_flow_tag
    await db.commit()
    return {"message": "现金流量标记已更新", "item_id": item_id, "cash_flow_tag": req.cash_flow_tag}


# ========== 辅助核算 ==========

class AuxiliaryUpdateRequest(BaseModel):
    """辅助核算更新请求"""
    item_id: int = Field(..., description="分录ID")
    auxiliary_accounting: Optional[dict] = Field(None, description="辅助核算: {customer, supplier, department, project, employee}")


@router.put("/items/{item_id}/auxiliary", summary="更新辅助核算")
async def update_auxiliary_accounting(
    item_id: int,
    req: AuxiliaryUpdateRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """更新凭证分录的辅助核算信息"""
    result = await db.execute(
        select(VoucherItem).join(Voucher).where(
            VoucherItem.id == item_id,
            Voucher.book_id == current_book.id,
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="分录不存在")

    item.auxiliary_accounting = req.auxiliary_accounting
    await db.commit()
    return {"message": "辅助核算已更新", "item_id": item_id, "auxiliary_accounting": req.auxiliary_accounting}


# ========== 批量现金流量标记 ==========

class BatchCashFlowRequest(BaseModel):
    """批量现金流量标记请求"""
    voucher_id: int = Field(..., description="凭证ID")
    item_tags: list[dict] = Field(..., description="[{item_id, cash_flow_tag}, ...]")


@router.post("/batch-cash-flow", summary="批量更新现金流量标记")
async def batch_update_cash_flow(
    req: BatchCashFlowRequest,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """批量更新凭证分录的现金流量标记"""
    result = await db.execute(
        select(VoucherItem).join(Voucher).where(
            VoucherItem.voucher_id == req.voucher_id,
            Voucher.book_id == current_book.id,
        )
    )
    items = {i.id: i for i in result.scalars().all()}

    updated = 0
    for tag_info in req.item_tags:
        item_id = tag_info.get("item_id")
        tag = tag_info.get("cash_flow_tag")
        if item_id in items:
            items[item_id].cash_flow_tag = tag
            updated += 1

    await db.commit()
    return {"message": f"已更新 {updated} 条分录的现金流量标记", "updated": updated}