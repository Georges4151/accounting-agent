"""
基于角色的权限控制 (RBAC) 模块
定义角色与权限的映射关系
"""
from typing import Dict, Set

# 角色权限映射
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {
        # 管理员权限
        "admin",
        # 用户管理
        "users:manage",
        # 系统配置
        "system:config",
        # 凭证管理
        "voucher:create",
        "voucher:review",
        "voucher:approve",
        "voucher:delete",
        # 报表
        "report:view",
        "report:export",
        # 税务
        "tax:calculate",
        "tax:declare",
        # 审批
        "expense:approve",
        # 模型切换
        "model:switch",
        # 联网搜索
        "search:web",
        # 审计
        "audit:view",
    },
    "accountant": {
        "voucher:create",
        "voucher:approve",
        "report:view",
        "report:export",
        "tax:calculate",
        "model:switch",
        "search:web",
    },
    "cashier": {
        "voucher:cashier_review",
        "report:view",
    },
    "reviewer": {
        "voucher:review",
        "voucher:approve",
        "expense:approve",
        "report:view",
        "audit:view",
    },
    "viewer": {
        "report:view",
    },
}

# 需要二次验证的敏感操作列表
SENSITIVE_OPERATIONS: list = [
    "voucher:delete",
    "users:manage",
    "system:config",
    "tax:declare",
    "model:switch",
]