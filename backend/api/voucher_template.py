"""
凭证模板管理 API 路由
提供模板的 CRUD 和模板应用功能
"""
import logging
from typing import Optional, List
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.voucher import Voucher, VoucherItem
from models.voucher_template import VoucherTemplate, VoucherTemplateItem
from auth.middleware import get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voucher-templates", tags=["凭证模板"])


# ========== 请求/响应模型 ==========

class TemplateItemCreate(BaseModel):
    """模板分录创建体"""
    account_code: str = Field(..., description="科目编码")
    account_name: str = Field(..., description="科目名称")
    description: str = Field(..., description="分录描述")
    debit_amount: float = Field(default=0, description="借方金额（可为0）")
    credit_amount: float = Field(default=0, description="贷方金额（可为0）")
    sort_order: int = Field(default=0, description="排序")


class TemplateCreate(BaseModel):
    """创建模板请求体"""
    name: str = Field(..., min_length=1, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    category: str = Field(default="其他", description="分类: 收入/支出/转账/其他")
    items: List[TemplateItemCreate] = Field(..., min_length=1, description="模板分录列表")


class TemplateUpdate(BaseModel):
    """更新模板请求体"""
    name: Optional[str] = Field(None, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    category: Optional[str] = Field(None, description="分类")
    items: Optional[List[TemplateItemCreate]] = Field(None, description="模板分录列表")


class TemplateItemResponse(BaseModel):
    """模板分录响应体"""
    id: int
    account_code: str
    account_name: str
    description: str
    debit_amount: float
    credit_amount: float
    sort_order: int

    class Config:
        from_attributes = True


class TemplateResponse(BaseModel):
    """模板响应体"""
    id: int
    name: str
    description: Optional[str]
    category: str
    is_default: bool
    created_by: int
    created_at: Optional[str]
    items: List[TemplateItemResponse] = []
    item_count: int = 0

    class Config:
        from_attributes = True


class TemplateListItem(BaseModel):
    """模板列表项"""
    id: int
    name: str
    description: Optional[str]
    category: str
    is_default: bool
    created_by: int
    created_at: Optional[str]
    item_count: int = 0

    class Config:
        from_attributes = True


class ApplyTemplateItem(BaseModel):
    """应用模板时对分录金额的覆盖"""
    account_code: str = Field(..., description="科目编码")
    debit_amount: Optional[float] = Field(None, description="借方金额覆盖")
    credit_amount: Optional[float] = Field(None, description="贷方金额覆盖")


class ApplyTemplateRequest(BaseModel):
    """应用模板请求体"""
    voucher_date: str = Field(..., description="凭证日期 YYYY-MM-DD")
    summary: Optional[str] = Field(None, description="凭证摘要，不传则使用模板描述")
    amount_overrides: Optional[List[ApplyTemplateItem]] = Field(None, description="金额覆盖列表")


def _generate_voucher_no() -> str:
    """生成凭证号"""
    now = datetime.now()
    return f"PZ-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}{now.microsecond // 1000:03d}"


# ========== API 端点 ==========

@router.get("", summary="获取模板列表")
async def list_templates(
    category: Optional[str] = Query(None, description="按分类筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取凭证模板列表，支持按分类筛选"""
    query = select(VoucherTemplate).order_by(VoucherTemplate.id.desc())
    if category:
        query = query.where(VoucherTemplate.category == category)

    result = await db.execute(query)
    templates = result.scalars().all()

    items = []
    for t in templates:
        items.append(
            TemplateListItem(
                id=t.id,
                name=t.name,
                description=t.description,
                category=t.category,
                is_default=t.is_default,
                created_by=t.created_by,
                created_at=t.created_at.isoformat() if t.created_at else None,
                item_count=len(t.items) if t.items else 0,
            )
        )

    return {"templates": items}


@router.post("", response_model=TemplateResponse, summary="创建模板")
async def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """创建凭证模板"""
    template = VoucherTemplate(
        name=template_data.name,
        description=template_data.description,
        category=template_data.category,
        is_default=False,
        created_by=current_user.id,
    )
    db.add(template)
    await db.flush()

    for item_data in template_data.items:
        item = VoucherTemplateItem(
            template_id=template.id,
            account_code=item_data.account_code,
            account_name=item_data.account_name,
            description=item_data.description,
            debit_amount=item_data.debit_amount,
            credit_amount=item_data.credit_amount,
            sort_order=item_data.sort_order,
        )
        db.add(item)

    await db.commit()
    await db.refresh(template)
    logger.info(f"用户 {current_user.username} 创建了模板 {template.name}")

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        is_default=template.is_default,
        created_by=template.created_by,
        created_at=template.created_at.isoformat() if template.created_at else None,
        items=[
            TemplateItemResponse(
                id=i.id,
                account_code=i.account_code,
                account_name=i.account_name,
                description=i.description,
                debit_amount=float(i.debit_amount),
                credit_amount=float(i.credit_amount),
                sort_order=i.sort_order,
            )
            for i in template.items
        ],
        item_count=len(template.items),
    )


@router.get("/{template_id}", response_model=TemplateResponse, summary="获取模板详情")
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取模板详情"""
    result = await db.execute(
        select(VoucherTemplate).where(VoucherTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        is_default=template.is_default,
        created_by=template.created_by,
        created_at=template.created_at.isoformat() if template.created_at else None,
        items=[
            TemplateItemResponse(
                id=i.id,
                account_code=i.account_code,
                account_name=i.account_name,
                description=i.description,
                debit_amount=float(i.debit_amount),
                credit_amount=float(i.credit_amount),
                sort_order=i.sort_order,
            )
            for i in template.items
        ],
        item_count=len(template.items),
    )


@router.put("/{template_id}", response_model=TemplateResponse, summary="更新模板")
async def update_template(
    template_id: int,
    template_data: TemplateUpdate,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """更新模板"""
    result = await db.execute(
        select(VoucherTemplate).where(VoucherTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    if template_data.name is not None:
        template.name = template_data.name
    if template_data.description is not None:
        template.description = template_data.description
    if template_data.category is not None:
        template.category = template_data.category

    if template_data.items is not None:
        # 删除旧分录
        for item in template.items:
            await db.delete(item)
        # 添加新分录
        for item_data in template_data.items:
            item = VoucherTemplateItem(
                template_id=template.id,
                account_code=item_data.account_code,
                account_name=item_data.account_name,
                description=item_data.description,
                debit_amount=item_data.debit_amount,
                credit_amount=item_data.credit_amount,
                sort_order=item_data.sort_order,
            )
            db.add(item)

    await db.commit()
    await db.refresh(template)
    logger.info(f"用户 {current_user.username} 更新了模板 {template.name}")

    return TemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        category=template.category,
        is_default=template.is_default,
        created_by=template.created_by,
        created_at=template.created_at.isoformat() if template.created_at else None,
        items=[
            TemplateItemResponse(
                id=i.id,
                account_code=i.account_code,
                account_name=i.account_name,
                description=i.description,
                debit_amount=float(i.debit_amount),
                credit_amount=float(i.credit_amount),
                sort_order=i.sort_order,
            )
            for i in template.items
        ],
        item_count=len(template.items),
    )


@router.delete("/{template_id}", summary="删除模板")
async def delete_template(
    template_id: int,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """删除模板"""
    result = await db.execute(
        select(VoucherTemplate).where(VoucherTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    if template.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="系统默认模板不可删除",
        )

    await db.delete(template)
    await db.commit()
    logger.info(f"用户 {current_user.username} 删除了模板 {template.name}")
    return {"message": "模板已删除"}


@router.post("/{template_id}/apply", summary="应用模板创建凭证")
async def apply_template(
    template_id: int,
    apply_data: ApplyTemplateRequest,
    current_user: User = Depends(require_permission("voucher:create")),
    db: AsyncSession = Depends(get_db),
):
    """根据模板创建凭证"""
    result = await db.execute(
        select(VoucherTemplate).where(VoucherTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

    if not template.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="模板没有分录，无法创建凭证",
        )

    # 构建金额覆盖映射
    override_map = {}
    if apply_data.amount_overrides:
        for ov in apply_data.amount_overrides:
            override_map[ov.account_code] = ov

    # 创建凭证
    summary = apply_data.summary or template.description or template.name
    voucher = Voucher(
        voucher_no=_generate_voucher_no(),
        voucher_date=date.fromisoformat(apply_data.voucher_date),
        summary=summary,
        status="draft",
        created_by=current_user.id,
    )
    db.add(voucher)
    await db.flush()

    # 根据模板分录创建凭证分录
    for t_item in template.items:
        ov = override_map.get(t_item.account_code)
        debit = ov.debit_amount if ov and ov.debit_amount is not None else float(t_item.debit_amount)
        credit = ov.credit_amount if ov and ov.credit_amount is not None else float(t_item.credit_amount)

        item = VoucherItem(
            voucher_id=voucher.id,
            account_code=t_item.account_code,
            account_name=t_item.account_name,
            description=t_item.description,
            debit_amount=debit,
            credit_amount=credit,
        )
        db.add(item)

    await db.commit()
    await db.refresh(voucher)
    logger.info(f"用户 {current_user.username} 使用模板 {template.name} 创建了凭证 {voucher.voucher_no}")

    return {
        "id": voucher.id,
        "voucher_no": voucher.voucher_no,
        "voucher_date": voucher.voucher_date.isoformat(),
        "summary": voucher.summary,
        "status": voucher.status,
        "created_by": voucher.created_by,
        "reviewed_by": voucher.reviewed_by,
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