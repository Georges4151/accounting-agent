"""
多币种管理 API
币种 CRUD + 汇率管理 + 汇兑计算
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from models.book import Book
from models.currency import Currency, ExchangeRate
from auth.middleware import get_current_user
from auth.book_context import get_current_book

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["多币种管理"])


# ========== 请求/响应模型 ==========

class CurrencyCreate(BaseModel):
    code: str = Field(..., description="币种代码")
    name: str = Field(..., description="币种名称")
    symbol: str = Field(..., description="货币符号")
    is_base: bool = Field(default=False, description="是否本位币")
    status: str = Field(default="active", description="状态")


class CurrencyUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    symbol: Optional[str] = None
    is_base: Optional[bool] = None
    status: Optional[str] = None


class ExchangeRateCreate(BaseModel):
    currency_code: str = Field(..., description="币种代码")
    rate_date: str = Field(..., description="汇率日期(YYYY-MM-DD)")
    rate: float = Field(..., description="汇率")
    rate_type: str = Field(default="middle", description="汇率类型")


class ExchangeRateBatch(BaseModel):
    rates: list[ExchangeRateCreate] = Field(..., description="汇率列表")


class ConvertRequest(BaseModel):
    from_currency: str = Field(..., description="原币种")
    to_currency: str = Field(..., description="目标币种")
    amount: float = Field(..., description="金额")
    date: Optional[str] = Field(default=None, description="汇率日期")


# ========== 币种管理 ==========

@router.get("/currencies", summary="获取币种列表")
async def list_currencies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取所有币种"""
    result = await db.execute(
        select(Currency).order_by(Currency.is_base.desc(), Currency.code)
    )
    currencies = result.scalars().all()
    return {
        "items": [
            {
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "symbol": c.symbol,
                "is_base": c.is_base,
                "status": c.status,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in currencies
        ]
    }


@router.post("/currencies", summary="添加币种")
async def create_currency(
    req: CurrencyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加新币种"""
    existing = await db.execute(
        select(Currency).where(Currency.code == req.code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"币种 {req.code} 已存在")

    if req.is_base:
        base_result = await db.execute(
            select(Currency).where(Currency.is_base == True)
        )
        base = base_result.scalar_one_or_none()
        if base:
            raise HTTPException(status_code=400, detail="本位币只能有一个，请先取消现有本位币")

    currency = Currency(
        code=req.code.upper(),
        name=req.name,
        symbol=req.symbol,
        is_base=req.is_base,
        status=req.status,
    )
    db.add(currency)
    await db.commit()
    await db.refresh(currency)
    return {"message": "添加成功", "id": currency.id}


@router.put("/currencies/{currency_id}", summary="更新币种")
async def update_currency(
    currency_id: int,
    req: CurrencyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新币种信息"""
    result = await db.execute(
        select(Currency).where(Currency.id == currency_id)
    )
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=404, detail="币种不存在")

    if req.code and req.code.upper() != currency.code:
        existing = await db.execute(
            select(Currency).where(Currency.code == req.code.upper())
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"币种 {req.code} 已存在")
        currency.code = req.code.upper()

    if req.is_base:
        base_result = await db.execute(
            select(Currency).where(Currency.is_base == True, Currency.id != currency_id)
        )
        base = base_result.scalar_one_or_none()
        if base:
            raise HTTPException(status_code=400, detail="本位币只能有一个，请先取消现有本位币")
        currency.is_base = True

    if req.name is not None:
        currency.name = req.name
    if req.symbol is not None:
        currency.symbol = req.symbol
    if req.status is not None:
        currency.status = req.status

    await db.commit()
    return {"message": "更新成功"}


@router.delete("/currencies/{currency_id}", summary="删除币种")
async def delete_currency(
    currency_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除币种"""
    result = await db.execute(
        select(Currency).where(Currency.id == currency_id)
    )
    currency = result.scalar_one_or_none()
    if not currency:
        raise HTTPException(status_code=404, detail="币种不存在")

    if currency.is_base:
        raise HTTPException(status_code=400, detail="不能删除本位币")

    await db.delete(currency)
    await db.commit()
    return {"message": "删除成功"}


# ========== 汇率管理 ==========

@router.get("/exchange-rates", summary="获取汇率列表")
async def list_exchange_rates(
    currency_code: Optional[str] = Query(None, description="币种代码"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """获取汇率列表，支持币种和日期筛选"""
    book_id = current_book.id
    conditions = []
    if book_id:
        conditions.append(
            (ExchangeRate.book_id == book_id) | (ExchangeRate.book_id == None)
        )
    if currency_code:
        conditions.append(ExchangeRate.currency_code == currency_code.upper())
    if start_date:
        conditions.append(ExchangeRate.rate_date >= date.fromisoformat(start_date))
    if end_date:
        conditions.append(ExchangeRate.rate_date <= date.fromisoformat(end_date))

    count_query = select(func.count()).select_from(ExchangeRate)
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = (await db.execute(count_query)).scalar()

    query = select(ExchangeRate).order_by(ExchangeRate.rate_date.desc(), ExchangeRate.currency_code)
    if conditions:
        query = query.where(and_(*conditions))
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    rates = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "currency_code": r.currency_code,
                "rate_date": r.rate_date.isoformat(),
                "rate": float(r.rate),
                "rate_type": r.rate_type,
                "book_id": r.book_id,
            }
            for r in rates
        ],
    }


@router.post("/exchange-rates", summary="添加汇率")
async def create_exchange_rate(
    req: ExchangeRateCreate,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """添加单条汇率"""
    book_id = current_book.id
    try:
        rate_date = date.fromisoformat(req.rate_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式不正确，应为YYYY-MM-DD")

    existing = await db.execute(
        select(ExchangeRate).where(
            ExchangeRate.currency_code == req.currency_code.upper(),
            ExchangeRate.rate_date == rate_date,
            ExchangeRate.rate_type == req.rate_type,
            (ExchangeRate.book_id == book_id) | (ExchangeRate.book_id == None),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该币种、日期、类型的汇率已存在")

    rate = ExchangeRate(
        currency_code=req.currency_code.upper(),
        rate_date=rate_date,
        rate=Decimal(str(req.rate)),
        rate_type=req.rate_type,
        book_id=book_id,
    )
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return {"message": "添加成功", "id": rate.id}


@router.post("/exchange-rates/batch", summary="批量导入汇率")
async def batch_import_rates(
    req: ExchangeRateBatch,
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """批量导入汇率"""
    book_id = current_book.id
    imported = 0
    skipped = 0
    errors = []

    for item in req.rates:
        try:
            rate_date = date.fromisoformat(item.rate_date)
            existing = await db.execute(
                select(ExchangeRate).where(
                    ExchangeRate.currency_code == item.currency_code.upper(),
                    ExchangeRate.rate_date == rate_date,
                    ExchangeRate.rate_type == item.rate_type,
                    (ExchangeRate.book_id == book_id) | (ExchangeRate.book_id == None),
                )
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue

            db.add(ExchangeRate(
                currency_code=item.currency_code.upper(),
                rate_date=rate_date,
                rate=Decimal(str(item.rate)),
                rate_type=item.rate_type,
                book_id=book_id,
            ))
            imported += 1
        except (ValueError, Exception) as e:
            errors.append(str(e))
            skipped += 1

    await db.commit()
    return {
        "message": f"导入完成: 成功 {imported} 条, 跳过 {skipped} 条",
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:10],
    }


@router.delete("/exchange-rates/{rate_id}", summary="删除汇率")
async def delete_exchange_rate(
    rate_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除汇率记录"""
    result = await db.execute(
        select(ExchangeRate).where(ExchangeRate.id == rate_id)
    )
    rate = result.scalar_one_or_none()
    if not rate:
        raise HTTPException(status_code=404, detail="汇率记录不存在")

    await db.delete(rate)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/exchange-rates/convert", summary="汇兑计算")
async def convert_currency(
    from_currency: str = Query(..., description="原币种"),
    to_currency: str = Query(..., description="目标币种"),
    amount: float = Query(..., description="金额"),
    rate_date: Optional[str] = Query(None, description="汇率日期(YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """汇兑计算"""
    book_id = current_book.id
    if from_currency.upper() == to_currency.upper():
        return {
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper(),
            "amount": amount,
            "converted_amount": amount,
            "rate": 1.0,
            "rate_date": rate_date,
        }

    target_date = date.fromisoformat(rate_date) if rate_date else date.today()

    # 获取本位币
    base_currency = await db.execute(
        select(Currency).where(Currency.is_base == True)
    )
    base = base_currency.scalar_one_or_none()
    base_code = base.code if base else "CNY"

    # 获取汇率
    conditions = [
        ExchangeRate.rate_date <= target_date,
        (ExchangeRate.book_id == book_id) | (ExchangeRate.book_id == None),
    ]
    if from_currency.upper() != base_code:
        from_rate_result = await db.execute(
            select(ExchangeRate).where(
                ExchangeRate.currency_code == from_currency.upper(),
                *conditions,
            ).order_by(ExchangeRate.rate_date.desc()).limit(1)
        )
        from_rate = from_rate_result.scalar_one_or_none()
        from_rate_val = float(from_rate.rate) if from_rate else 1.0
    else:
        from_rate_val = 1.0

    if to_currency.upper() != base_code:
        to_rate_result = await db.execute(
            select(ExchangeRate).where(
                ExchangeRate.currency_code == to_currency.upper(),
                *conditions,
            ).order_by(ExchangeRate.rate_date.desc()).limit(1)
        )
        to_rate = to_rate_result.scalar_one_or_none()
        to_rate_val = float(to_rate.rate) if to_rate else 1.0
    else:
        to_rate_val = 1.0

    if from_rate_val == 0:
        raise HTTPException(status_code=400, detail="无法获取原币种汇率")

    cross_rate = to_rate_val / from_rate_val
    converted = round(amount * cross_rate, 2)

    return {
        "from_currency": from_currency.upper(),
        "to_currency": to_currency.upper(),
        "amount": amount,
        "converted_amount": converted,
        "rate": round(cross_rate, 8),
        "rate_date": target_date.isoformat(),
    }


@router.get("/exchange-rates/profit-loss", summary="计算汇兑损益")
async def get_profit_loss(
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
    current_user: User = Depends(get_current_user),
    current_book: Book = Depends(get_current_book),
    db: AsyncSession = Depends(get_db),
):
    """计算指定期间的汇兑损益"""
    book_id = current_book.id
    if not book_id:
        raise HTTPException(status_code=400, detail="请先选择账套")

    try:
        s_date = date.fromisoformat(start_date)
        e_date = date.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式不正确")

    # 获取期间末的汇率
    conditions = [
        ExchangeRate.rate_date <= e_date,
        (ExchangeRate.book_id == book_id) | (ExchangeRate.book_id == None),
    ]

    rates_result = await db.execute(
        select(ExchangeRate.currency_code, ExchangeRate.rate)
        .where(*conditions)
        .order_by(ExchangeRate.rate_date.desc())
    )
    all_rates = rates_result.all()

    latest_rates = {}
    for code, rate in all_rates:
        if code not in latest_rates:
            latest_rates[code] = float(rate)

    return {
        "period": f"{start_date} ~ {end_date}",
        "latest_rates": latest_rates,
        "message": "汇兑损益需要在凭证层面计算，此接口返回期间末汇率供参考",
        "items": [
            {"currency_code": code, "rate": rate}
            for code, rate in latest_rates.items()
        ],
    }