"""
税务计算服务
从凭证数据中自动计算各项税费
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional, Any

from sqlalchemy import select, func, extract, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.voucher import Voucher, VoucherItem
from models.tax import TaxRecord, TaxSummary

logger = logging.getLogger(__name__)

# 默认税率配置
DEFAULT_RATES = {
    "增值税": Decimal("0.13"),
    "企业所得税": Decimal("0.25"),
    "附加税": Decimal("0.12"),  # 城建税7% + 教育费附加3% + 地方教育附加2%
    "印花税": Decimal("0.0005"),  # 0.05%
    "其他": Decimal("0"),
}

# 收入类科目名称关键词
REVENUE_KEYWORDS = ["主营业务收入", "其他业务收入", "营业收入", "销售收入"]
# 进项税额科目关键词
INPUT_TAX_KEYWORDS = ["应交税费-应交增值税(进项税额)", "进项税额"]


def _get_period_range(period: str):
    """从 YYYY-MM 格式生成该月的起止日期"""
    try:
        year, month = period.split("-")
        year_int = int(year)
        month_int = int(month)
        start_date = date(year_int, month_int, 1)
        # 计算下个月第一天
        if month_int == 12:
            end_date = date(year_int + 1, 1, 1)
        else:
            end_date = date(year_int, month_int + 1, 1)
        return start_date, end_date
    except (ValueError, IndexError):
        raise ValueError(f"无效的期间格式: {period}，应为 YYYY-MM")


async def _get_voucher_items_in_period(
    db: AsyncSession, period: str
) -> list[VoucherItem]:
    """获取指定期间内已审核/已过账凭证的所有分录"""
    start_date, end_date = _get_period_range(period)

    result = await db.execute(
        select(VoucherItem)
        .join(Voucher, VoucherItem.voucher_id == Voucher.id)
        .where(
            Voucher.voucher_date >= start_date,
            Voucher.voucher_date < end_date,
            Voucher.status.in_(["reviewed", "posted"]),
        )
    )
    return list(result.scalars().all())


async def calculate_vat(
    db: AsyncSession, period: str, rate: Decimal | None = None
) -> Dict[str, Any]:
    """计算增值税

    增值税 = 销项税额 - 进项税额
    销项税额 = 主营业务收入 * 税率
    进项税额 = 从进项税额科目汇总
    """
    if rate is None:
        rate = DEFAULT_RATES["增值税"]

    items = await _get_voucher_items_in_period(db, period)

    # 汇总收入类科目的贷方金额
    total_revenue = Decimal("0")
    has_revenue = False
    for item in items:
        for kw in REVENUE_KEYWORDS:
            if kw in item.account_name:
                total_revenue += item.credit_amount
                has_revenue = True
                break

    # 汇总进项税额科目的借方金额
    total_input_tax = Decimal("0")
    has_input_tax = False
    for item in items:
        for kw in INPUT_TAX_KEYWORDS:
            if kw in item.account_name:
                total_input_tax += item.debit_amount
                has_input_tax = True
                break

    output_tax = total_revenue * rate
    vat_amount = output_tax - total_input_tax

    return {
        "tax_type": "增值税",
        "period": period,
        "revenue": float(total_revenue),
        "output_tax": float(output_tax),
        "input_tax": float(total_input_tax),
        "tax_amount": float(vat_amount),
        "tax_rate": float(rate),
        "taxable_amount": float(total_revenue),
        "has_data": has_revenue or has_input_tax,
    }


async def calculate_income_tax(
    db: AsyncSession, period: str, rate: Decimal | None = None
) -> Dict[str, Any]:
    """计算企业所得税

    简化计算：利润总额 = 所有收入 - 所有成本费用，然后 * 税率
    """
    if rate is None:
        rate = DEFAULT_RATES["企业所得税"]

    items = await _get_voucher_items_in_period(db, period)

    # 汇总所有贷方金额（收入）和借方金额（成本费用）
    total_credit = Decimal("0")
    total_debit = Decimal("0")
    revenue_items = Decimal("0")
    expense_items = Decimal("0")

    for item in items:
        is_revenue = False
        for kw in REVENUE_KEYWORDS:
            if kw in item.account_name:
                is_revenue = True
                break
        if is_revenue:
            revenue_items += item.credit_amount
        else:
            total_credit += item.credit_amount
            total_debit += item.debit_amount

    # 利润 = 所有贷方(收入) - 所有借方(成本费用)
    total_income = total_credit
    total_expense = total_debit
    profit = total_income - total_expense

    if profit < 0:
        profit = Decimal("0")

    income_tax = profit * rate

    return {
        "tax_type": "企业所得税",
        "period": period,
        "total_income": float(total_income),
        "total_expense": float(total_expense),
        "profit": float(profit),
        "tax_amount": float(income_tax),
        "tax_rate": float(rate),
        "taxable_amount": float(profit),
        "has_data": float(total_income) > 0 or float(total_expense) > 0,
    }


async def calculate_surtax(
    db: AsyncSession, period: str, rate: Decimal | None = None
) -> Dict[str, Any]:
    """计算附加税

    附加税 = 增值税 * 12%（城建税7% + 教育费附加3% + 地方教育附加2%）
    """
    if rate is None:
        rate = DEFAULT_RATES["附加税"]

    # 先计算增值税
    vat_result = await calculate_vat(db, period)
    vat_amount = Decimal(str(vat_result["tax_amount"]))

    surtax_amount = vat_amount * rate

    return {
        "tax_type": "附加税",
        "period": period,
        "vat_amount": float(vat_amount),
        "surtax_amount": float(surtax_amount),
        "tax_amount": float(surtax_amount),
        "tax_rate": float(rate),
        "taxable_amount": float(vat_amount),
        "has_data": vat_result["has_data"],
        "breakdown": {
            "城建税(7%)": float(vat_amount * Decimal("0.07")),
            "教育费附加(3%)": float(vat_amount * Decimal("0.03")),
            "地方教育附加(2%)": float(vat_amount * Decimal("0.02")),
        },
    }


async def calculate_stamp_tax(
    db: AsyncSession, period: str, rate: Decimal | None = None
) -> Dict[str, Any]:
    """计算印花税（简化：按合同金额 * 0.05%）"""
    if rate is None:
        rate = DEFAULT_RATES["印花税"]

    items = await _get_voucher_items_in_period(db, period)

    total_contract = Decimal("0")
    for item in items:
        if "合同" in item.account_name or "采购" in item.account_name or "销售" in item.account_name:
            total_contract += item.debit_amount + item.credit_amount

    stamp_tax = total_contract * rate

    return {
        "tax_type": "印花税",
        "period": period,
        "contract_amount": float(total_contract),
        "tax_amount": float(stamp_tax),
        "tax_rate": float(rate),
        "taxable_amount": float(total_contract),
        "has_data": float(total_contract) > 0,
    }


TAX_CALCULATORS = {
    "增值税": calculate_vat,
    "企业所得税": calculate_income_tax,
    "附加税": calculate_surtax,
    "印花税": calculate_stamp_tax,
}


async def get_tax_summary(
    db: AsyncSession, period: str
) -> Dict[str, Any]:
    """获取指定期间的税务汇总"""
    start_date, end_date = _get_period_range(period)

    # 查询所有已保存的税务记录
    result = await db.execute(
        select(TaxRecord).where(TaxRecord.tax_period == period)
    )
    records = result.scalars().all()

    total_calculated = Decimal("0")
    total_paid = Decimal("0")
    total_remaining = Decimal("0")
    tax_details = []

    for r in records:
        total_calculated += r.tax_amount
        total_paid += r.paid_amount
        total_remaining += r.remaining_amount
        tax_details.append({
            "tax_type": r.tax_type,
            "calculated_tax": float(r.tax_amount),
            "paid_amount": float(r.paid_amount),
            "remaining": float(r.remaining_amount),
            "status": r.status,
            "effective_tax_rate": float(r.tax_rate) if r.taxable_amount > 0 else 0,
        })

    # 计算实际税负率
    items = await _get_voucher_items_in_period(db, period)
    total_revenue = Decimal("0")
    for item in items:
        for kw in REVENUE_KEYWORDS:
            if kw in item.account_name:
                total_revenue += item.credit_amount
                break

    effective_rate = round(float(total_calculated / total_revenue), 4) if total_revenue > 0 else 0

    return {
        "period": period,
        "total_revenue": float(total_revenue),
        "total_calculated_tax": float(total_calculated),
        "total_paid": float(total_paid),
        "total_remaining": float(total_remaining),
        "effective_tax_rate": effective_rate,
        "details": tax_details,
    }


async def get_tax_analysis(
    db: AsyncSession, year: int
) -> Dict[str, Any]:
    """获取年度税负分析"""
    monthly_data = []
    total_year_tax = Decimal("0")
    total_year_revenue = Decimal("0")

    for month in range(1, 13):
        period = f"{year}-{month:02d}"
        summary = await get_tax_summary(db, period)
        monthly_data.append({
            "period": period,
            "total_tax": summary["total_calculated_tax"],
            "total_revenue": summary["total_revenue"],
            "effective_rate": summary["effective_tax_rate"],
        })
        total_year_tax += Decimal(str(summary["total_calculated_tax"]))
        total_year_revenue += Decimal(str(summary["total_revenue"]))

    # 按税种汇总
    tax_type_breakdown = {}
    for month in range(1, 13):
        period = f"{year}-{month:02d}"
        result = await db.execute(
            select(TaxRecord).where(TaxRecord.tax_period == period)
        )
        records = result.scalars().all()
        for r in records:
            if r.tax_type not in tax_type_breakdown:
                tax_type_breakdown[r.tax_type] = 0
            tax_type_breakdown[r.tax_type] += float(r.tax_amount)

    year_effective_rate = round(
        float(total_year_tax / total_year_revenue), 4
    ) if total_year_revenue > 0 else 0

    return {
        "year": year,
        "monthly": monthly_data,
        "tax_type_breakdown": [
            {"tax_type": k, "amount": v}
            for k, v in tax_type_breakdown.items()
        ],
        "total_year_tax": float(total_year_tax),
        "total_year_revenue": float(total_year_revenue),
        "year_effective_rate": year_effective_rate,
        "industry_average_rate": 0.035,  # 行业平均税负率参考值
    }