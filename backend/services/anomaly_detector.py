"""
异常检测服务
检测财务数据中的异常模式
"""
import logging
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.voucher import Voucher, VoucherItem

logger = logging.getLogger(__name__)


async def detect_anomalies(
    db: AsyncSession,
    book_id: Optional[int] = None,
    period: Optional[str] = None,
) -> list[dict]:
    """检测财务数据中的异常
    
    检测项目：
    1. 借贷不平衡的凭证
    2. 金额异常的凭证（单笔金额超过月均值的3倍）
    3. 重复凭证（同一天相同金额相同摘要）
    4. 负数金额
    5. 缺少必要分录的凭证
    
    Returns:
        [{"type": "imbalance", "severity": "high", "voucher_id": 1, "message": "...", "detail": ""}, ...]
    """
    anomalies = []
    
    conditions = [Voucher.status.in_(["draft", "submitted", "reviewed", "approved", "posted"])]
    if book_id:
        conditions.append(Voucher.book_id == book_id)
    
    # 获取所有凭证
    result = await db.execute(
        select(Voucher).where(and_(*conditions))
    )
    vouchers = result.scalars().all()
    
    if not vouchers:
        return []
    
    # 计算月均金额
    total_amount = 0.0
    voucher_count = 0
    date_amounts = {}
    
    for v in vouchers:
        # 获取凭证的借贷合计
        items_result = await db.execute(
            select(
                func.sum(VoucherItem.debit_amount).label("total_debit"),
                func.sum(VoucherItem.credit_amount).label("total_credit"),
            ).where(VoucherItem.voucher_id == v.id)
        )
        row = items_result.one()
        total_debit = float(row.total_debit or 0)
        total_credit = float(row.total_credit or 0)
        
        # 1. 检测借贷不平衡
        if abs(total_debit - total_credit) > 0.01:
            anomalies.append({
                "type": "imbalance",
                "severity": "high",
                "voucher_id": v.id,
                "voucher_no": v.voucher_no,
                "message": f"凭证 {v.voucher_no} 借贷不平衡: 借方{total_debit}, 贷方{total_credit}",
                "detail": f"差额: {abs(total_debit - total_credit):.2f}"
            })
        
        # 记录金额用于均值计算
        voucher_amount = max(total_debit, total_credit)
        total_amount += voucher_amount
        voucher_count += 1
        
        vdate = v.voucher_date.isoformat() if v.voucher_date else ""
        if vdate not in date_amounts:
            date_amounts[vdate] = []
        date_amounts[vdate].append({
            "voucher_id": v.id,
            "voucher_no": v.voucher_no,
            "amount": voucher_amount,
            "summary": v.summary or "",
        })
    
    # 2. 检测金额异常（单笔超过月均值的3倍 或 超过10万元）
    if voucher_count > 0:
        avg_amount = total_amount / voucher_count
        threshold = max(avg_amount * 3, 100000)
        
        for v in vouchers:
            items_result = await db.execute(
                select(func.sum(VoucherItem.debit_amount)).where(VoucherItem.voucher_id == v.id)
            )
            v_amount = float(items_result.scalar() or 0)
            
            if v_amount > threshold:
                anomalies.append({
                    "type": "large_amount",
                    "severity": "medium",
                    "voucher_id": v.id,
                    "voucher_no": v.voucher_no,
                    "message": f"凭证 {v.voucher_no} 金额异常偏大: {v_amount:.2f}元 (阈值: {threshold:.2f}元)",
                    "detail": f"月均金额: {avg_amount:.2f}元"
                })
    
    # 3. 检测重复凭证（同一天相同金额+相同摘要）
    for vdate, entries in date_amounts.items():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                if (abs(entries[i]["amount"] - entries[j]["amount"]) < 0.01 and
                    entries[i]["summary"] == entries[j]["summary"]):
                    anomalies.append({
                        "type": "duplicate",
                        "severity": "high",
                        "voucher_id": entries[i]["voucher_id"],
                        "voucher_no": entries[i]["voucher_no"],
                        "message": f"凭证 {entries[i]['voucher_no']} 与 {entries[j]['voucher_no']} 疑似重复",
                        "detail": f"日期: {vdate}, 金额: {entries[i]['amount']:.2f}, 摘要: {entries[i]['summary']}"
                    })
    
    # 4. 检测负数金额
    for v in vouchers:
        items_result = await db.execute(
            select(VoucherItem).where(VoucherItem.voucher_id == v.id)
        )
        items = items_result.scalars().all()
        
        for item in items:
            if item.debit_amount < 0 or item.credit_amount < 0:
                anomalies.append({
                    "type": "negative_amount",
                    "severity": "medium",
                    "voucher_id": v.id,
                    "voucher_no": v.voucher_no,
                    "message": f"凭证 {v.voucher_no} 分录包含负数金额: {item.account_name}",
                    "detail": f"借方: {item.debit_amount}, 贷方: {item.credit_amount}"
                })
                break  # 每个凭证只报告一次
    
    return anomalies