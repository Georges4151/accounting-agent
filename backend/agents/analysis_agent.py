"""
分析 Agent
负责财务分析和异常预警
"""
from typing import List, Optional
from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel

from .base_agent import BaseAgent


class AnalysisAgent(BaseAgent):
    """分析 Agent，负责财务分析和异常预警"""

    def __init__(self, llm: BaseChatModel, tools: Optional[List] = None):
        analysis_tools = [
            calculate_financial_ratios,
            trend_analysis,
            anomaly_detection,
        ]
        system_prompt = """你是一个财务分析师，负责对企业的财务数据进行分析和预警。

你可以进行以下分析：
- 财务比率分析（流动比率、资产负债率、ROE等）
- 趋势分析（同比、环比）
- 异常检测（大额异常支出、收入波动等）

请根据数据给出专业的分析结论和改进建议。"""
        super().__init__(llm=llm, tools=tools or analysis_tools, system_prompt=system_prompt)


# ========== 分析工具函数 ==========

@tool
def calculate_financial_ratios(
    current_assets: float,
    current_liabilities: float,
    total_assets: float,
    total_liabilities: float,
    net_profit: float,
    equity: float,
) -> str:
    """计算财务比率

    Args:
        current_assets: 流动资产
        current_liabilities: 流动负债
        total_assets: 总资产
        total_liabilities: 总负债
        net_profit: 净利润
        equity: 所有者权益
    """
    current_ratio = current_assets / current_liabilities if current_liabilities else 0
    debt_ratio = total_liabilities / total_assets if total_assets else 0
    roe = net_profit / equity if equity else 0

    return (
        f"财务比率分析:\n"
        f"  流动比率: {current_ratio:.2f} (标准 > 2.0)\n"
        f"  资产负债率: {debt_ratio:.2%} (标准 < 70%)\n"
        f"  ROE (净资产收益率): {roe:.2%}"
    )


@tool
def trend_analysis(metric_name: str, periods: str) -> str:
    """趋势分析

    Args:
        metric_name: 指标名称
        periods: 各期数据 JSON 字符串
    """
    return f"趋势分析 - {metric_name}（功能开发中）"


@tool
def anomaly_detection(data_description: str) -> str:
    """异常检测

    Args:
        data_description: 数据描述
    """
    return f"异常检测 - {data_description}（功能开发中）"