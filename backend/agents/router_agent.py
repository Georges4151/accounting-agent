"""
路由 Agent
负责意图识别和任务分发，将用户请求路由到对应的专业 Agent
"""
from typing import List, Optional
from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel

from .base_agent import BaseAgent


class RouterAgent(BaseAgent):
    """路由 Agent，负责意图识别和任务分发"""

    def __init__(self, llm: BaseChatModel, tools: Optional[List] = None):
        router_tools = [
            route_to_bookkeeping,
            route_to_report,
            route_to_tax,
            route_to_analysis,
            route_to_qa,
        ]
        system_prompt = """你是一个智能路由助手，负责分析用户意图并将任务分发到合适的专业 Agent。

请根据用户的输入，判断应该调用哪个工具：

- **route_to_bookkeeping**: 记账相关操作，如录入凭证、记录收支、费用报销等
- **route_to_report**: 报表查询，如资产负债表、利润表、现金流量表等
- **route_to_tax**: 税务相关，如增值税计算、所得税计算、税务申报等
- **route_to_analysis**: 财务分析，如指标分析、趋势分析、异常检测等
- **route_to_qa**: 知识问答，如财务制度咨询、政策解读等

请根据用户输入选择最合适的工具，并用中文描述你的路由决策。"""
        super().__init__(llm=llm, tools=tools or router_tools, system_prompt=system_prompt)


# ========== 路由工具函数 ==========

@tool
def route_to_bookkeeping(description: str) -> str:
    """将用户请求路由到记账 Agent

    Args:
        description: 记账任务描述
    """
    return f"[ROUTE:bookkeeping] {description}"


@tool
def route_to_report(description: str) -> str:
    """将用户请求路由到报表 Agent

    Args:
        description: 报表任务描述
    """
    return f"[ROUTE:report] {description}"


@tool
def route_to_tax(description: str) -> str:
    """将用户请求路由到税务 Agent

    Args:
        description: 税务任务描述
    """
    return f"[ROUTE:tax] {description}"


@tool
def route_to_analysis(description: str) -> str:
    """将用户请求路由到分析 Agent

    Args:
        description: 分析任务描述
    """
    return f"[ROUTE:analysis] {description}"


@tool
def route_to_qa(description: str) -> str:
    """将用户请求路由到问答 Agent

    Args:
        description: 问答任务描述
    """
    return f"[ROUTE:qa] {description}"