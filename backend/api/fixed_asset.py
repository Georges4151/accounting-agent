"""
固定资产管理 API
"""
import logging
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.fixed_asset import FixedAsset, DepreciationRecord
from models.voucher import Voucher, VoucherItem, Account
from api.voucher import _generate_voucher_no
from auth.middleware import get_current_user
from auth.book_context import get_current_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fixed-assets", tags=["固定资产"])


# ========== 请求/响应模型 ==========

class AssetCreate(BaseModel):
    asset_code: str = Field(..., min_length=1)
    asset_name: str = Field(..., min_length=1)
    category: str = Field(..., description="房屋建筑/机器设备/运输工具/电子设备/其他")
    quantity: int = Field(1, ge=1)
    unit: str = "台"
    purchase_date: str
    original_value: float = Field(..., gt=0)
    salvage_value: float = 0
    useful_life_months: int = Field(..., ge=1)
    description: str | None = None


class AssetUpdate(BaseModel):
    asset_name: str | None = None
    category: str | None = None
    status: str | None = None
    description: str | None = None


class AssetResponse(BaseModel):
    id: int
    asset_code: str
    asset_name: str
    category: str
    quantity: int
    unit: str
    purchase_date: str
    original_value: float
    salvage_value: float
    useful_life_months: int
    monthly_depreciation: float
    accumulated_depreciation: float
    net_value: float
    depreciation_method: str
    status: str
    description: str | None = None
    created_at: str | None = None


class DepreciationResult(BaseModel):
    asset_id: int
    asset_name: str
    depreciation_amount: float
    period: str
    voucher_id: int | None = None


# ========== API 端点 ==========


async def _run_depreciation_for_book(
    book_id: int,
    period: str,
    current_user_id: int,
    db: AsyncSession,
    skip_existing: bool = True,
) -> dict:
    """核心折旧逻辑，可被端点调用也可被自动任务调用"""
    period_date = date.fromisoformat(period + "-01")
    period_first_day = period_date

    # 获取启用中的资产
    result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.book_id == book_id,
            FixedAsset.status == "in_use",
        )
    )
    assets = result.scalars().all()

    if not assets:
        return {"message": "无需要计提折旧的资产", "results": [], "skipped": 0, "depreciated": 0}

    results = []
    voucher_items = []
    total_depreciation = 0
    skipped_count = 0

    for asset in assets:
        # 校验：折旧期不能早于资产购置日期
        if asset.purchase_date and period_first_day < asset.purchase_date:
            logger.warning(
                f"资产 {asset.asset_name}({asset.asset_code}) 购置于 {asset.purchase_date}，"
                f"不能计提 {period} 折旧"
            )
            skipped_count += 1
            continue

        # 检查是否已计提该期间
        if skip_existing:
            existing = await db.execute(
                select(DepreciationRecord).where(
                    DepreciationRecord.asset_id == asset.id,
                    DepreciationRecord.period == period,
                )
            )
            if existing.scalar_one_or_none():
                skipped_count += 1
                continue

        # 检查是否已充分折旧（净值已降至残值或以下）
        if asset.net_value <= asset.salvage_value:
            skipped_count += 1
            continue

        # 计算本期折旧额
        # 达到使用年限时，最后一期折旧 = 当前净值 - 残值
        purchase_date = asset.purchase_date
        months_used = (period_date.year - purchase_date.year) * 12 + (period_date.month - purchase_date.month)
        is_last_period = months_used >= asset.useful_life_months

        remaining = asset.net_value - asset.salvage_value - asset.monthly_depreciation
        if remaining < 0 or is_last_period:
            # 最后一期或净值不足一月折旧额：折旧至残值
            dep_amount = round(asset.net_value - asset.salvage_value, 2)
        else:
            dep_amount = asset.monthly_depreciation

        if dep_amount <= 0:
            skipped_count += 1
            continue

        # 更新资产
        acc_before = asset.accumulated_depreciation
        asset.accumulated_depreciation = round(acc_before + dep_amount, 2)
        asset.net_value = round(asset.original_value - asset.accumulated_depreciation, 2)

        # 折旧完成后标记为已提足
        if asset.net_value <= asset.salvage_value:
            asset.status = "fully_depreciated"
            logger.info(f"资产 {asset.asset_name}({asset.asset_code}) 已提足折旧，净值={asset.net_value}")

        # 记录折旧
        db.add(DepreciationRecord(
            asset_id=asset.id,
            book_id=book_id,
            period=period,
            depreciation_amount=dep_amount,
            accumulated_before=acc_before,
            accumulated_after=asset.accumulated_depreciation,
        ))

        voucher_items.append({
            "account_code": asset.dep_account_code,
            "account_name": "累计折旧",
            "debit_amount": 0,
            "credit_amount": dep_amount,
            "description": f"{asset.asset_name}折旧",
        })
        total_depreciation += dep_amount
        results.append(DepreciationResult(
            asset_id=asset.id,
            asset_name=asset.asset_name,
            depreciation_amount=dep_amount,
            period=period,
        ))

    if not results:
        await db.commit()
        return {
            "message": f"该期间已计提完毕或无需要计提的资产（跳过 {skipped_count} 项）",
            "results": [],
            "skipped": skipped_count,
            "depreciated": 0,
        }

    # 生成折旧凭证
    voucher = Voucher(
        voucher_no=_generate_voucher_no(),
        voucher_date=period_date,
        summary=f"{period} 固定资产折旧",
        status="draft",
        book_id=book_id,
        created_by=current_user_id,
    )
    db.add(voucher)
    await db.flush()

    # 借方：管理费用/制造费用-折旧费
    db.add(VoucherItem(
        voucher_id=voucher.id,
        account_code="6602",
        account_name="管理费用",
        description=f"{period} 固定资产折旧",
        debit_amount=round(total_depreciation, 2),
        credit_amount=0,
    ))

    # 贷方：累计折旧
    for item in voucher_items:
        db.add(VoucherItem(
            voucher_id=voucher.id,
            account_code=item["account_code"],
            account_name=item["account_name"],
            description=item["description"],
            debit_amount=item["debit_amount"],
            credit_amount=item["credit_amount"],
        ))

    await db.commit()

    for r in results:
        r.voucher_id = voucher.id

    return {
        "message": f"计提折旧完成，共 {len(results)} 项资产（跳过 {skipped_count} 项），生成凭证 {voucher.voucher_no}",
        "voucher_id": voucher.id,
        "voucher_no": voucher.voucher_no,
        "total_depreciation": round(total_depreciation, 2),
        "results": [r.model_dump() for r in results],
        "skipped": skipped_count,
        "depreciated": len(results),
    }

@router.get("", summary="获取固定资产列表")
async def list_assets(
    category: str | None = Query(None, description="资产类别"),
    status: str | None = Query(None, description="状态"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取固定资产列表"""
    book_id = current_book.id

    conditions = [FixedAsset.book_id == book_id]
    if category:
        conditions.append(FixedAsset.category == category)
    if status:
        conditions.append(FixedAsset.status == status)

    result = await db.execute(
        select(FixedAsset)
        .where(and_(*conditions))
        .order_by(FixedAsset.asset_code)
    )
    assets = result.scalars().all()

    return {
        "items": [
            AssetResponse(
                id=a.id,
                asset_code=a.asset_code,
                asset_name=a.asset_name,
                category=a.category,
                quantity=a.quantity,
                unit=a.unit,
                purchase_date=a.purchase_date.isoformat(),
                original_value=a.original_value,
                salvage_value=a.salvage_value,
                useful_life_months=a.useful_life_months,
                monthly_depreciation=a.monthly_depreciation,
                accumulated_depreciation=a.accumulated_depreciation,
                net_value=a.net_value,
                depreciation_method=a.depreciation_method,
                status=a.status,
                description=a.description,
                created_at=a.created_at.isoformat() if a.created_at else None,
            )
            for a in assets
        ],
        "summary": {
            "total_original": sum(a.original_value for a in assets),
            "total_depreciation": sum(a.accumulated_depreciation for a in assets),
            "total_net": sum(a.net_value for a in assets),
            "count": len(assets),
        },
    }


@router.post("", summary="新增固定资产")
async def create_asset(
    data: AssetCreate,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """新增固定资产卡片"""
    book_id = current_book.id

    # 检查编码唯一性
    existing = await db.execute(
        select(FixedAsset).where(
            FixedAsset.book_id == book_id,
            FixedAsset.asset_code == data.asset_code,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"资产编码 {data.asset_code} 已存在")

    # 计算月折旧额（直线法）
    monthly_dep = round(
        (data.original_value - data.salvage_value) / data.useful_life_months, 2
    )

    asset = FixedAsset(
        book_id=book_id,
        asset_code=data.asset_code,
        asset_name=data.asset_name,
        category=data.category,
        quantity=data.quantity,
        unit=data.unit,
        purchase_date=date.fromisoformat(data.purchase_date),
        original_value=data.original_value,
        salvage_value=data.salvage_value,
        useful_life_months=data.useful_life_months,
        monthly_depreciation=monthly_dep,
        accumulated_depreciation=0,
        net_value=data.original_value,
        depreciation_method="straight_line",
        status="in_use",
        description=data.description,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    # 补录资产：自动补提购置月到上月之间的折旧
    purchase_date = date.fromisoformat(data.purchase_date)
    today = date.today()
    current_month = today.replace(day=1)
    purchase_month = purchase_date.replace(day=1)
    auto_depreciation_months = []

    if purchase_month < current_month:
        # 从购置月开始，逐月补提
        month = purchase_month
        while month < current_month:
            period_str = month.strftime("%Y-%m")
            try:
                dep_result = await _run_depreciation_for_book(
                    book_id=book_id,
                    period=period_str,
                    current_user_id=current_user.id,
                    db=db,
                    skip_existing=True,
                )
                auto_depreciation_months.append({
                    "period": period_str,
                    "depreciated": dep_result.get("depreciated", 0),
                })
            except Exception as e:
                logger.warning(f"补提折旧 {period_str} 失败: {e}")
            # 下个月
            if month.month == 12:
                month = month.replace(year=month.year + 1, month=1)
            else:
                month = month.replace(month=month.month + 1)

    # 补提折旧后刷新资产对象，获取最新累计折旧和净值
    await db.refresh(asset)

    response_data = AssetResponse(
        id=asset.id,
        asset_code=asset.asset_code,
        asset_name=asset.asset_name,
        category=asset.category,
        quantity=asset.quantity,
        unit=asset.unit,
        purchase_date=asset.purchase_date.isoformat(),
        original_value=asset.original_value,
        salvage_value=asset.salvage_value,
        useful_life_months=asset.useful_life_months,
        monthly_depreciation=asset.monthly_depreciation,
        accumulated_depreciation=asset.accumulated_depreciation,
        net_value=asset.net_value,
        depreciation_method=asset.depreciation_method,
        status=asset.status,
        description=asset.description,
        created_at=asset.created_at.isoformat() if asset.created_at else None,
    )

    if auto_depreciation_months:
        logger.info(
            f"补录资产 {asset.asset_name}，自动补提 {len(auto_depreciation_months)} 个月折旧: "
            f"{', '.join(m['period'] for m in auto_depreciation_months)}"
        )
        return {
            **response_data.model_dump(),
            "auto_depreciated": True,
            "auto_depreciation_months": auto_depreciation_months,
            "message": f"资产创建成功，已自动补提 {len(auto_depreciation_months)} 个月折旧",
        }

    return response_data


@router.put("/{asset_id}", summary="更新固定资产")
async def update_asset(
    asset_id: int,
    data: AssetUpdate,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """更新固定资产信息"""
    book_id = current_book.id
    result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.id == asset_id,
            FixedAsset.book_id == book_id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    if data.asset_name is not None:
        asset.asset_name = data.asset_name
    if data.category is not None:
        asset.category = data.category
    if data.status is not None:
        asset.status = data.status
    if data.description is not None:
        asset.description = data.description

    await db.commit()
    return {"message": "更新成功"}


@router.delete("/{asset_id}", summary="删除固定资产")
async def delete_asset(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """删除固定资产（仅当无折旧记录时）"""
    book_id = current_book.id
    result = await db.execute(
        select(FixedAsset).where(
            FixedAsset.id == asset_id,
            FixedAsset.book_id == book_id,
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")

    # 检查是否有折旧记录
    dep_result = await db.execute(
        select(func.count()).select_from(DepreciationRecord).where(
            DepreciationRecord.asset_id == asset_id
        )
    )
    if dep_result.scalar() > 0:
        raise HTTPException(status_code=400, detail="该资产已有折旧记录，无法删除")

    await db.delete(asset)
    await db.commit()
    return {"message": "删除成功"}


@router.post("/depreciate", summary="计提折旧")
async def calculate_depreciation(
    period: str = Query(..., description="折旧期间 YYYY-MM"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """计提指定期间的折旧并生成凭证，支持重复调用（自动跳过已计提资产）"""
    return await _run_depreciation_for_book(
        book_id=current_book.id,
        period=period,
        current_user_id=current_user.id,
        db=db,
        skip_existing=True,
    )


@router.get("/{asset_id}/depreciation-history", summary="折旧历史")
async def get_depreciation_history(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取资产折旧历史"""
    result = await db.execute(
        select(DepreciationRecord)
        .where(DepreciationRecord.asset_id == asset_id)
        .order_by(DepreciationRecord.period.desc())
    )
    records = result.scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "period": r.period,
                "depreciation_amount": r.depreciation_amount,
                "accumulated_before": r.accumulated_before,
                "accumulated_after": r.accumulated_after,
                "voucher_id": r.voucher_id,
            }
            for r in records
        ],
    }