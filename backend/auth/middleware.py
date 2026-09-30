"""
认证中间件模块
提供用户认证和权限校验的 FastAPI 依赖
"""
import logging
import time
import json
from typing import List, Optional, Callable
from functools import wraps

from fastapi import Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from database import get_db, async_session_maker
from auth.jwt_handler import JWTHandler
from models.user import User
from models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# HTTP Bearer 认证方案
security = HTTPBearer()

# Token 黑名单（内存存储，生产环境应使用 Redis）
_token_blacklist: set = set()


def is_token_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中"""
    return token in _token_blacklist


def add_to_blacklist(token: str) -> None:
    """将 token 添加到黑名单"""
    _token_blacklist.add(token)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从请求中提取并验证当前用户"""
    token = credentials.credentials

    # 检查 token 是否已注销
    if is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已失效，请重新登录",
        )

    # 验证 token
    try:
        payload = JWTHandler.verify_token(token, token_type="access")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        )

    user_id = int(payload.get("sub"))
    token_version = payload.get("ver", 1)

    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    # 检查 token 版本（用于强制登出和密码修改后使旧 token 失效）
    if token_version < user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 已失效，请重新登录",
        )

    return user


def require_permission(permission: str):
    """权限校验装饰器工厂函数，返回一个 FastAPI 依赖"""

    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        from auth.rbac import ROLE_PERMISSIONS

        role = current_user.role
        allowed = ROLE_PERMISSIONS.get(role, set())

        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要: {permission}",
            )

        return current_user

    return permission_checker


def require_role(*roles: str):
    """角色检查装饰器，要求用户拥有指定角色之一"""

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下角色之一: {', '.join(roles)}",
            )
        return current_user

    return role_checker


def require_any_permission(*permissions: str):
    """权限检查装饰器，要求用户拥有任一指定权限"""

    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        from auth.rbac import ROLE_PERMISSIONS

        role = current_user.role
        allowed = ROLE_PERMISSIONS.get(role, set())

        if not any(p in allowed for p in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要以下权限之一: {', '.join(permissions)}",
            )

        return current_user

    return permission_checker


def sensitive_operation(
    current_user: User = Depends(get_current_user),
) -> User:
    """敏感操作检查，要求用户启用 2FA（如果已配置）"""
    from auth.rbac import SENSITIVE_OPERATIONS

    # 如果用户启用了 2FA，后续可以在此处添加二次验证逻辑
    # 当前仅记录，不强制阻断
    return current_user


# ========== 审计日志中间件 ==========

# 路径到操作类型的映射
_ACTION_MAP = {
    ("POST", "login"): "login",
    ("POST", "logout"): "logout",
    ("POST", "refresh"): "refresh",
    ("POST", "upload"): "upload",
    ("POST", "recognize"): "api_call",
    ("POST", "generate-voucher"): "create",
    ("POST", ""): "create",
    ("PUT", ""): "update",
    ("PATCH", ""): "update",
    ("DELETE", ""): "delete",
}

# 不需要记录审计日志的路径
_SKIP_AUDIT_PATHS = {
    "/api/auth/refresh",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def _map_action(method: str, path: str) -> str:
    """根据 HTTP 方法和路径映射操作类型"""
    for (m, keyword), action in _ACTION_MAP.items():
        if method == m and keyword in path:
            return action
    if method == "GET":
        return "api_call"
    return "other"


def _map_resource(path: str) -> str:
    """根据路径映射资源类型"""
    if "/auth/" in path:
        return "认证"
    if "/invoices" in path:
        return "发票"
    if "/vouchers" in path or "/voucher" in path:
        return "凭证"
    if "/accounts" in path:
        return "科目"
    if "/reports" in path or "/report" in path:
        return "报表"
    if "/knowledge" in path:
        return "知识库"
    if "/chat" in path:
        return "AI助手"
    if "/users" in path:
        return "用户"
    if "/api-keys" in path:
        return "API密钥"
    if "/conversations" in path:
        return "对话"
    if "/audit" in path:
        return "审计"
    return "系统"


def _map_operation_category(method: str, path: str) -> str:
    """根据方法和路径映射操作分类"""
    path_lower = path.lower()

    if "/auth/login" in path_lower:
        return "user/login"
    if "/auth/logout" in path_lower:
        return "user/logout"
    if "/auth/change-password" in path_lower:
        return "user/change_password"
    if "/auth/sessions" in path_lower:
        return "user/session"

    if "/vouchers" in path_lower:
        if method == "POST" and "submit" in path_lower:
            return "voucher/submit"
        if method == "POST" and "review" in path_lower:
            return "voucher/review"
        if method == "POST" and "reject" in path_lower:
            return "voucher/reject"
        if method == "DELETE":
            return "voucher/delete"
        if method == "PUT":
            return "voucher/update"
        if method == "POST":
            return "voucher/create"
        return "voucher/read"

    if "/users" in path_lower:
        if method == "POST":
            return "user/create"
        if method == "PUT" and "reset-password" in path_lower:
            return "user/reset_password"
        if method == "PUT" and "toggle-active" in path_lower:
            return "user/toggle"
        if method == "PUT":
            return "user/update"
        if method == "DELETE":
            return "user/delete"
        return "user/read"

    if "/reports" in path_lower:
        if "export" in path_lower:
            return "report/export"
        return "report/view"

    if "/invoices" in path_lower:
        if method == "POST":
            return "invoice/upload"
        return "invoice/read"

    if "/knowledge" in path_lower:
        if method == "POST":
            return "knowledge/create"
        if method == "DELETE":
            return "knowledge/delete"
        return "knowledge/read"

    if "/chat" in path_lower:
        return "chat/message"

    if "/api-keys" in path_lower:
        if method == "POST":
            return "apikey/create"
        if method == "DELETE":
            return "apikey/delete"
        return "apikey/read"

    if "/conversations" in path_lower:
        return "conversation/manage"

    if "/import" in path_lower or "/export" in path_lower:
        return "data/transfer"

    return f"{method.lower()}/other"


def _extract_resource_id(path: str) -> Optional[int]:
    """从路径中提取资源 ID"""
    import re
    # 匹配 /api/xxx/{id} 或 /api/xxx/{id}/action
    match = re.search(r"/(\d+)(?:/|$)", path)
    if match:
        return int(match.group(1))
    return None


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP"""
    # 优先从 X-Forwarded-For 获取
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # 其次从 X-Real-IP 获取
    real_ip = request.headers.get("X-Real-IP", "")
    if real_ip:
        return real_ip.strip()
    # 最后使用 client.host
    if request.client:
        return request.client.host
    return "unknown"


class AuditLogMiddleware(BaseHTTPMiddleware):
    """审计日志中间件：自动记录 API 请求"""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # 跳过不需要记录的路由
        if request.url.path in _SKIP_AUDIT_PATHS:
            return await call_next(request)

        start_time = time.time()
        status_code = 500
        detail = None
        request_body = None

        # 读取请求体（仅 POST/PUT/PATCH/DELETE）
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body_text = body_bytes.decode("utf-8", errors="replace")
                    request_body = body_text[:1000]  # 截断到1000字符
                # 重新设置请求体，使下游处理能正常读取
                async def receive():
                    return {"type": "http.request", "body": body_bytes}
                request._receive = receive
            except Exception:
                pass

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            status_code = 500
            detail = str(e)[:500]
            raise
        finally:
            # 异步写入审计日志（不阻塞响应）
            elapsed = time.time() - start_time
            try:
                await self._write_audit_log(
                    request, status_code, elapsed, detail, request_body
                )
            except Exception:
                pass  # 审计日志写入失败不影响主流程

    async def _write_audit_log(
        self,
        request: Request,
        status_code: int,
        elapsed: float,
        detail: str | None,
        request_body: str | None,
    ):
        """写入审计日志到数据库"""
        try:
            # 提取用户信息
            username = "anonymous"
            user_id = 0
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    payload = JWTHandler.verify_token(token, token_type="access")
                    user_id = int(payload.get("sub", 0))
                    username = payload.get("username", str(user_id))
                except Exception:
                    pass

            # 提取请求信息
            method = request.method
            path = request.url.path
            client_ip = _get_client_ip(request)
            user_agent = (request.headers.get("User-Agent", "") or "")[:255]

            action = _map_action(method, path)
            resource = _map_resource(path)
            operation_category = _map_operation_category(method, path)
            affected_resource_id = _extract_resource_id(path)
            is_success = "success" if 200 <= status_code < 400 else "failure"

            if detail is None:
                detail = f"{method} {path} {status_code} ({elapsed:.2f}s)"

            async with async_session_maker() as session:
                log = AuditLog(
                    user_id=user_id,
                    username=username,
                    action=action,
                    resource=resource,
                    detail=detail,
                    ip_address=client_ip,
                    user_agent=user_agent,
                    status=is_success,
                    operation_category=operation_category,
                    affected_resource_id=affected_resource_id,
                    request_body=request_body,
                    response_status=status_code,
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.warning(f"审计日志写入失败: {e}")