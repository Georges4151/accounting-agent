"""
密码策略验证模块
提供密码强度校验功能
"""
import re
from typing import List, Tuple


def validate_password_strength(password: str) -> Tuple[bool, List[str]]:
    """
    验证密码强度

    规则:
    - 最少 8 个字符
    - 至少 1 个大写字母
    - 至少 1 个小写字母
    - 至少 1 个数字
    - 至少 1 个特殊字符

    Args:
        password: 待验证的密码

    Returns:
        (是否通过, 错误信息列表)
    """
    errors = []

    if len(password) < 8:
        errors.append("密码长度至少为 8 个字符")

    if not re.search(r"[A-Z]", password):
        errors.append("密码必须包含至少 1 个大写字母")

    if not re.search(r"[a-z]", password):
        errors.append("密码必须包含至少 1 个小写字母")

    if not re.search(r"\d", password):
        errors.append("密码必须包含至少 1 个数字")

    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password):
        errors.append("密码必须包含至少 1 个特殊字符")

    return len(errors) == 0, errors


def get_password_strength_level(password: str) -> str:
    """
    评估密码强度等级

    Returns:
        'weak', 'medium', 'strong'
    """
    score = 0

    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[a-z]", password):
        score += 1
    if re.search(r"\d", password):
        score += 1
    if re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?~`]", password):
        score += 1
    if len(password) >= 16:
        score += 1

    if score <= 2:
        return "weak"
    elif score <= 4:
        return "medium"
    else:
        return "strong"