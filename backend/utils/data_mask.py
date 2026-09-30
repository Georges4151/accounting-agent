"""
敏感金额脱敏工具模块
根据用户角色对金额数据进行脱敏处理
"""
from typing import Any, Dict, List, Optional, Union

from config.settings import settings

# 需要脱敏的角色
MASKED_ROLES = {"viewer"}

# 脱敏替换值
MASK_REPLACEMENT = "****"


def is_mask_enabled() -> bool:
    """检查是否启用了金额脱敏"""
    return getattr(settings, "ENABLE_AMOUNT_MASKING", True)


def should_mask(user_role: str) -> bool:
    """判断指定角色是否需要脱敏"""
    if not is_mask_enabled():
        return False
    return user_role in MASKED_ROLES


def mask_amount(amount: Any, user_role: str) -> str:
    """
    对单个金额进行脱敏

    Args:
        amount: 原始金额
        user_role: 用户角色

    Returns:
        脱敏后的字符串或格式化后的原始金额
    """
    if should_mask(user_role):
        return MASK_REPLACEMENT
    if amount is None:
        return "0.00"
    return str(amount)


def mask_voucher_item(item: Dict[str, Any], user_role: str) -> Dict[str, Any]:
    """对凭证分录中的金额进行脱敏"""
    if not should_mask(user_role):
        return item
    item = dict(item)
    if "debit_amount" in item:
        item["debit_amount"] = MASK_REPLACEMENT if item["debit_amount"] else "0.00"
    if "credit_amount" in item:
        item["credit_amount"] = MASK_REPLACEMENT if item["credit_amount"] else "0.00"
    return item


def mask_voucher_response(voucher_data: Dict[str, Any], user_role: str) -> Dict[str, Any]:
    """
    对凭证响应数据中的金额进行脱敏

    Args:
        voucher_data: 凭证响应数据
        user_role: 用户角色

    Returns:
        脱敏后的数据
    """
    if not should_mask(user_role):
        return voucher_data

    voucher_data = dict(voucher_data)

    # 脱敏分录中的金额
    if "items" in voucher_data:
        voucher_data["items"] = [
            mask_voucher_item(item, user_role) for item in voucher_data["items"]
        ]

    return voucher_data


def mask_voucher_list_item(item: Dict[str, Any], user_role: str) -> Dict[str, Any]:
    """对凭证列表项中的合计金额进行脱敏"""
    if not should_mask(user_role):
        return item
    item = dict(item)
    if "total_debit" in item:
        item["total_debit"] = MASK_REPLACEMENT
    if "total_credit" in item:
        item["total_credit"] = MASK_REPLACEMENT
    return item


def mask_voucher_list(voucher_list: List[Dict[str, Any]], user_role: str) -> List[Dict[str, Any]]:
    """对凭证列表中的金额进行脱敏"""
    if not should_mask(user_role):
        return voucher_list
    return [mask_voucher_list_item(item, user_role) for item in voucher_list]


def mask_report_item(item: Dict[str, Any], user_role: str) -> Dict[str, Any]:
    """对报表数据项中的金额字段进行脱敏"""
    if not should_mask(user_role):
        return item
    item = dict(item)
    amount_fields = [
        "ending_balance", "beginning_balance", "total_debit", "total_credit",
        "current_amount", "cumulative_amount", "amount", "net_profit",
        "beginning_debit", "beginning_credit", "current_debit", "current_credit",
        "ending_debit", "ending_credit",
    ]
    for field in amount_fields:
        if field in item:
            item[field] = MASK_REPLACEMENT
    return item


def mask_report_response(report_data: Dict[str, Any], user_role: str) -> Dict[str, Any]:
    """
    对报表响应数据中的金额进行脱敏

    Args:
        report_data: 报表响应数据
        user_role: 用户角色

    Returns:
        脱敏后的数据
    """
    if not should_mask(user_role):
        return report_data

    report_data = dict(report_data)

    # 脱敏汇总金额
    summary_fields = [
        "total_assets", "total_liabilities", "total_equity",
        "total_liabilities_and_equity", "total_revenue", "total_expenses",
        "net_profit",
    ]
    for field in summary_fields:
        if field in report_data:
            report_data[field] = MASK_REPLACEMENT

    # 脱敏各明细项
    list_fields = [
        "assets", "liabilities", "equity", "revenue", "expenses",
        "items", "operating", "investing", "financing",
    ]
    for field in list_fields:
        if field in report_data and isinstance(report_data[field], list):
            report_data[field] = [
                mask_report_item(item, user_role) for item in report_data[field]
            ]

    return report_data