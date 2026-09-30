"""
认证 API 路由
处理登录、刷新令牌、退出和密码修改
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, model_validator

from database import get_db
from models.user import User
from auth.jwt_handler import JWTHandler
from auth.middleware import get_current_user, add_to_blacklist
from config.settings import settings
from utils.rate_limiter import login_rate_limiter
from utils.password_policy import validate_password_strength

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["认证"])


# ========== 请求/响应模型 ==========

class LoginRequest(BaseModel):
    """登录请求体"""
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class TokenResponse(BaseModel):
    """令牌响应体"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    user: "UserInfoResponse | None" = Field(default=None, description="用户信息")
    remaining_attempts: int | None = Field(default=None, description="剩余登录尝试次数")


class RefreshRequest(BaseModel):
    """刷新令牌请求体"""
    refresh_token: str = Field(..., description="刷新令牌")


class ChangePasswordRequest(BaseModel):
    """修改密码请求体"""
    old_password: str = Field(..., min_length=1, description="旧密码")
    new_password: str = Field(
        ..., min_length=settings.PASSWORD_MIN_LENGTH, description="新密码"
    )


class UserInfoResponse(BaseModel):
    """用户信息响应体"""
    id: int
    username: str
    real_name: str
    role: str
    department: str | None
    email: str | None
    is_active: bool
    two_factor_enabled: bool
    token_version: int = 1
    avatar: str | None = None

    class Config:
        from_attributes = True

    @model_validator(mode="after")
    def transform_avatar(self):
        """将 avatar 文件名转换为完整 URL 路径"""
        if self.avatar and not self.avatar.startswith("/"):
            self.avatar = f"/uploads/avatars/{self.avatar}"
        return self


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    device: str
    ip_address: str
    login_time: str
    is_current: bool


class PasswordStrengthResponse(BaseModel):
    """密码强度检查响应"""
    valid: bool
    errors: List[str]
    strength: str


# ========== API 端点 ==========

@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录，验证密码并返回双令牌"""
    # 获取客户端 IP
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    # 速率限制检查
    allowed, remaining = login_rate_limiter.check(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"登录尝试次数过多，请 {settings.RATE_LIMIT_WINDOW_MINUTES} 分钟后再试",
        )

    # 查询用户
    result = await db.execute(
        select(User).where(User.username == login_data.username)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # 增加失败计数
        remaining_after = login_rate_limiter.increment(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"用户名或密码错误（剩余尝试次数: {remaining_after}）",
        )

    # 检查账户是否被锁定
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining_minutes = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"账户已被锁定，请在 {remaining_minutes} 分钟后重试",
        )

    # 检查账户是否启用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    # 验证密码
    if not JWTHandler.verify_password(login_data.password, user.password_hash):
        # 增加登录失败次数
        user.login_attempts += 1
        if user.login_attempts >= settings.ACCOUNT_LOCK_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.LOCKOUT_MINUTES
            )
            logger.warning(f"用户 {user.username} 因连续 {settings.ACCOUNT_LOCK_ATTEMPTS} 次登录失败被锁定")
        await db.commit()

        # 增加 IP 速率限制计数
        remaining_after = login_rate_limiter.increment(client_ip)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"用户名或密码错误（剩余尝试次数: {remaining_after}）",
        )

    # 登录成功，重置所有限制
    login_rate_limiter.reset(client_ip)
    user.login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(timezone.utc)
    user.login_ip = client_ip

    # 生成令牌
    access_token = JWTHandler.create_access_token(
        user.id, user.role, user.username, user.token_version
    )
    refresh_token = JWTHandler.create_refresh_token(user.id)

    await db.commit()
    logger.info(f"用户 {user.username} 登录成功 (IP: {client_ip})")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserInfoResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse, summary="刷新令牌")
async def refresh_token(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """使用刷新令牌获取新的访问令牌"""
    try:
        payload = JWTHandler.verify_token(refresh_data.refresh_token, token_type="refresh")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效或已过期",
        )

    user_id = int(payload.get("sub"))
    # 查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )

    # 生成新的令牌对
    new_access_token = JWTHandler.create_access_token(
        user.id, user.role, user.username, user.token_version
    )
    new_refresh_token = JWTHandler.create_refresh_token(user.id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=UserInfoResponse.model_validate(user),
    )


@router.post("/logout", summary="退出登录")
async def logout(
    current_user: User = Depends(get_current_user),
    request: Request = None,
):
    """退出登录，将当前 token 加入黑名单"""
    # 从请求中提取 Authorization header
    auth_header = request.headers.get("Authorization") if request else None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        add_to_blacklist(token)
        logger.info(f"用户 {current_user.username} 已退出登录")
    return {"message": "退出成功"}


@router.get("/me", response_model=UserInfoResponse, summary="获取当前用户信息")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """获取当前登录用户的详细信息"""
    return UserInfoResponse.model_validate(current_user)


@router.put("/change-password", summary="修改密码")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户的登录密码"""
    # 验证旧密码
    if not JWTHandler.verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码不正确",
        )

    # 验证新密码强度
    valid, errors = validate_password_strength(password_data.new_password)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码不符合安全要求: {'; '.join(errors)}",
        )

    # 更新密码并递增 token 版本（使所有旧 token 失效）
    current_user.password_hash = JWTHandler.hash_password(password_data.new_password)
    current_user.token_version += 1
    await db.commit()
    logger.info(f"用户 {current_user.username} 修改了密码，token 版本已更新")
    return {"message": "密码修改成功，所有设备已登出，请重新登录"}


@router.get("/sessions", summary="获取当前活跃会话")
async def get_sessions(
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的活跃会话列表（当前仅显示当前会话）"""
    # 当前简化实现：仅返回当前会话信息
    # 生产环境应使用 Redis 等存储会话信息
    return {
        "sessions": [
            {
                "session_id": "current",
                "device": "当前设备",
                "ip_address": current_user.login_ip or "unknown",
                "login_time": current_user.last_login.isoformat() if current_user.last_login else None,
                "is_current": True,
            }
        ],
        "total": 1,
    }


@router.post("/logout-all", summary="登出所有设备")
async def logout_all(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """使所有设备的会话失效（递增 token_version）"""
    # 递增 token 版本，使所有旧 token 失效
    current_user.token_version += 1
    await db.commit()

    # 将当前 token 加入黑名单
    auth_header = request.headers.get("Authorization") if request else None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        add_to_blacklist(token)

    logger.info(f"用户 {current_user.username} 已登出所有设备")
    return {"message": "所有设备已登出，请重新登录"}


@router.post("/check-password-strength", response_model=PasswordStrengthResponse, summary="检查密码强度")
async def check_password_strength(
    password_data: dict,
):
    """检查密码强度（无需登录）"""
    password = password_data.get("password", "")
    valid, errors = validate_password_strength(password)
    from utils.password_policy import get_password_strength_level
    strength = get_password_strength_level(password)
    return PasswordStrengthResponse(valid=valid, errors=errors, strength=strength)