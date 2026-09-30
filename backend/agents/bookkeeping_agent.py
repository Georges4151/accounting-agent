"""
记账 Agent
根据自然语言描述自动生成记账凭证
"""
import json
import logging
from typing import List, Optional

from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class BookkeepingAgent(BaseAgent):
    """记账 Agent，根据自然语言生成记账凭证"""

    def __init__(self, llm: BaseChatModel, tools: Optional[List] = None):
        bookkeeping_tools = [
            query_accounts,
            create_voucher,
            validate_balance,
        ]
        system_prompt = """你是一个专业会计，负责根据用户的自然语言描述自动生成记账凭证。

你需要：
1. 分析用户描述的业务场景
2. 确定涉及的会计科目
3. 确定借贷方向和金额
4. 生成完整的记账凭证分录
5. 确保借贷平衡

在处理过程中：
- 使用 query_accounts 工具查询可用的会计科目
- 使用 create_voucher 工具创建凭证
- 使用 validate_balance 工具校验借贷平衡

请严格遵循《企业会计准则》进行记账。"""
        super().__init__(llm=llm, tools=tools or bookkeeping_tools, system_prompt=system_prompt)


# ========== 记账工具函数 ==========

@tool
def query_accounts(keyword: str) -> str:
    """查询会计科目，返回匹配的科目列表

    Args:
        keyword: 科目名称或编码关键词
    """
    import asyncio
    from database import async_session_maker
    from sqlalchemy import select
    from models.voucher import Account

    async def _query():
        async with async_session_maker() as db:
            result = await db.execute(
                select(Account).where(
                    (Account.account_name.ilike(f"%{keyword}%"))
                    | (Account.account_code.ilike(f"%{keyword}%"))
                ).where(Account.is_active == True).limit(20)
            )
            accounts = result.scalars().all()
            if not accounts:
                return f"未找到包含 '{keyword}' 的科目"
            lines = []
            for acc in accounts:
                lines.append(
                    f"  {acc.account_code} {acc.account_name} "
                    f"（{acc.account_type}，余额方向: {acc.balance_direction}）"
                )
            return "找到以下科目:\n" + "\n".join(lines)

    try:
        return asyncio.run(_query())
    except Exception as e:
        logger.error(f"查询科目失败: {e}")
        return f"查询科目时出错: {str(e)}"


@tool
def validate_balance(debit_total: float, credit_total: float) -> str:
    """校验借贷平衡

    Args:
        debit_total: 借方合计
        credit_total: 贷方合计
    """
    if abs(debit_total - credit_total) < 0.01:
        return "借贷平衡 ✓"
    else:
        diff = debit_total - credit_total
        direction = "借" if diff > 0 else "贷"
        return f"借贷不平衡！{direction}方差额: {abs(diff):.2f}"


@tool
def create_voucher(
    date: str,
    summary: str,
    items: str,
) -> str:
    """创建记账凭证（由 Agent 调用，实际创建在 ai-generate 端点完成）

    Args:
        date: 凭证日期 YYYY-MM-DD
        summary: 凭证摘要
        items: 分录列表 JSON 字符串，格式: [{"account_code":"1001","account_name":"库存现金","description":"描述","debit_amount":1000,"credit_amount":0}, ...]
    """
    try:
        items_data = json.loads(items) if isinstance(items, str) else items
        item_count = len(items_data)
        total_debit = sum(i.get("debit_amount", 0) for i in items_data)
        total_credit = sum(i.get("credit_amount", 0) for i in items_data)

        if abs(total_debit - total_credit) > 0.01:
            return f"凭证创建失败：借贷不平衡（借方 {total_debit}，贷方 {total_credit}）"

        return (
            f"凭证记录已创建: {date} {summary}\n"
            f"  共 {item_count} 条分录，借方合计 {total_debit}，贷方合计 {total_credit}\n"
            f"  借贷平衡 ✓"
        )
    except json.JSONDecodeError as e:
        return f"分录数据格式错误: {str(e)}"
    except Exception as e:
        return f"创建凭证时出错: {str(e)}"