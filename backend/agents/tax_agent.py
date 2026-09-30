"""
税务 Agent
负责税务计算和申报辅助
"""
from typing import List, Optional
from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel

from .base_agent import BaseAgent


class TaxAgent(BaseAgent):
    """税务 Agent，负责税务计算和申报辅助"""

    def __init__(self, llm: BaseChatModel, tools: Optional[List] = None):
        tax_tools = [
            calculate_vat,
            calculate_income_tax,
            calculate_surtax,
        ]
        system_prompt = """你是一个税务专家，负责帮助用户进行税务计算和申报。

你可以处理以下税务：
- 增值税（VAT）计算
- 企业所得税计算
- 附加税（城建税、教育费附加等）计算

请根据用户提供的业务数据，准确计算各项税费，并给出申报建议。
注意：你的建议仅供参考，最终以税务机关核定为准。"""
        super().__init__(llm=llm, tools=tools or tax_tools, system_prompt=system_prompt)


# ========== 税务工具函数 ==========

@tool
def calculate_vat(
    sales_amount: float,
    purchase_amount: float,
    vat_rate: float = 0.13,
) -> str:
    """计算增值税

    Args:
        sales_amount: 销售额
        purchase_amount: 进项税额
        vat_rate: 增值税率
    """
    output_vat = sales_amount * vat_rate
    input_vat = purchase_amount * vat_rate if purchase_amount > 0 else 0
    payable = output_vat - input_vat
    return (
        f"增值税计算:\n"
        f"  销项税额: {output_vat:,.2f}\n"
        f"  进项税额: {input_vat:,.2f}\n"
        f"  应缴税额: {payable:,.2f}"
    )


@tool
def calculate_income_tax(profit: float, tax_rate: float = 0.25) -> str:
    """计算企业所得税

    Args:
        profit: 应纳税所得额
        tax_rate: 所得税率
    """
    tax = profit * tax_rate if profit > 0 else 0
    return (
        f"企业所得税计算:\n"
        f"  应纳税所得额: {profit:,.2f}\n"
        f"  适用税率: {tax_rate * 100}%\n"
        f"  应缴税额: {tax:,.2f}"
    )


@tool
def calculate_surtax(vat_amount: float, city_rate: float = 0.07, education_rate: float = 0.03) -> str:
    """计算附加税

    Args:
        vat_amount: 增值税额
        city_rate: 城建税率
        education_rate: 教育费附加率
    """
    city_tax = vat_amount * city_rate
    education_tax = vat_amount * education_rate
    total = city_tax + education_tax
    return (
        f"附加税计算:\n"
        f"  城建税 ({city_rate*100}%): {city_tax:,.2f}\n"
        f"  教育费附加 ({education_rate*100}%): {education_tax:,.2f}\n"
        f"  合计: {total:,.2f}"
    )