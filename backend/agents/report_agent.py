"""
报表 Agent
根据用户请求生成各类财务报表
"""
from typing import List, Optional
from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel

from .base_agent import BaseAgent


class ReportAgent(BaseAgent):
    """报表 Agent，负责生成财务报表"""

    def __init__(self, llm: BaseChatModel, tools: Optional[List] = None):
        report_tools = [
            get_account_balances,
            generate_balance_sheet,
            generate_income_statement,
            generate_cash_flow,
        ]
        system_prompt = """你是一个财务报表专家，负责根据用户请求生成各类财务报表。

你可以生成以下报表：
- 资产负债表（Balance Sheet）
- 利润表（Income Statement）
- 现金流量表（Cash Flow Statement）
- 科目余额表（Account Ledger）

请根据用户需求，选择合适的报表类型，并提供清晰的数据展示和分析。"""
        super().__init__(llm=llm, tools=tools or report_tools, system_prompt=system_prompt)


# ========== 报表工具函数 ==========

@tool
def get_account_balances(start_date: str, end_date: str) -> str:
    """获取科目余额

    Args:
        start_date: 开始日期
        end_date: 结束日期
    """
    return f"获取 {start_date} 至 {end_date} 的科目余额（功能开发中）"


@tool
def generate_balance_sheet(report_date: str) -> str:
    """生成资产负债表

    Args:
        report_date: 报表日期
    """
    return f"资产负债表 - {report_date}（功能开发中）"


@tool
def generate_income_statement(start_date: str, end_date: str) -> str:
    """生成利润表

    Args:
        start_date: 开始日期
        end_date: 结束日期
    """
    return f"利润表 {start_date} ~ {end_date}（功能开发中）"


@tool
def generate_cash_flow(start_date: str, end_date: str) -> str:
    """生成现金流量表

    Args:
        start_date: 开始日期
        end_date: 结束日期
    """
    return f"现金流量表 {start_date} ~ {end_date}（功能开发中）"