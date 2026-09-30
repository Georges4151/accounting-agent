"""
用户管理 API 路由
提供用户 CRUD 操作，仅限管理员
"""
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from auth.middleware import get_current_user, require_permission
from auth.jwt_handler import JWTHandler
from utils.password_policy import validate_password_strength

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["用户管理"])

# 头像上传目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AVATAR_DIR = os.path.join(BASE_DIR, "uploads", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB


# ========== 请求/响应模型 ==========

class CreateUserRequest(BaseModel):
    """创建用户请求体"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    real_name: str = Field(..., min_length=1, max_length=50, description="真实姓名")
    password: str = Field(..., min_length=8, description="密码")
    role: str = Field(..., description="角色: admin/accountant/reviewer/viewer")
    department: Optional[str] = Field(None, max_length=50, description="部门")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")


class UpdateUserRequest(BaseModel):
    """更新用户请求体"""
    real_name: Optional[str] = Field(None, min_length=1, max_length=50, description="真实姓名")
    role: Optional[str] = Field(None, description="角色")
    department: Optional[str] = Field(None, max_length=50, description="部门")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")


class ResetPasswordRequest(BaseModel):
    """重置密码请求体"""
    password: str = Field(..., min_length=6, description="新密码")


class UserListItem(BaseModel):
    """用户列表项"""
    id: int
    username: str
    real_name: str
    role: str
    department: str | None
    email: str | None
    is_active: bool
    last_login_at: str | None
    created_at: str
    avatar: str | None = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    """分页响应"""
    total: int
    page: int
    page_size: int
    items: list[UserListItem]


# ========== API 端点 ==========

@router.get("", response_model=PaginatedResponse, summary="用户列表")
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    role: Optional[str] = Query(None, description="按角色筛选"),
    _: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """获取用户列表，支持分页和筛选"""
    # 构建查询条件
    query = select(User)
    count_query = select(func.count(User.id))

    filters = []
    if keyword:
        keyword_filter = or_(
            User.username.ilike(f"%{keyword}%"),
            User.real_name.ilike(f"%{keyword}%"),
            User.email.ilike(f"%{keyword}%"),
        )
        filters.append(keyword_filter)
    if role:
        filters.append(User.role == role)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    offset = (page - 1) * page_size
    query = query.order_by(User.id.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    items = [
        UserListItem(
            id=u.id,
            username=u.username,
            real_name=u.real_name,
            role=u.role,
            department=u.department,
            email=u.email,
            is_active=u.is_active,
            last_login_at=u.last_login.isoformat() if u.last_login else None,
            created_at=u.created_at.isoformat() if u.created_at else "",
            avatar=f"/uploads/avatars/{u.avatar}" if u.avatar else None,
        )
        for u in users
    ]

    return PaginatedResponse(total=total, page=page, page_size=page_size, items=items)


@router.post("", summary="创建用户")
async def create_user(
    user_data: CreateUserRequest,
    _: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """创建新用户"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    # 验证角色是否合法
    valid_roles = {"admin", "accountant", "reviewer", "viewer"}
    if user_data.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色，有效角色: {', '.join(valid_roles)}",
        )

    # 验证密码强度
    valid_pw, pw_errors = validate_password_strength(user_data.password)
    if not valid_pw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码不符合安全要求: {'; '.join(pw_errors)}",
        )

    new_user = User(
        username=user_data.username,
        real_name=user_data.real_name,
        password_hash=JWTHandler.hash_password(user_data.password),
        role=user_data.role,
        department=user_data.department,
        email=user_data.email,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"管理员创建了新用户: {new_user.username}")
    return {"message": "用户创建成功", "user_id": new_user.id}


@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: int,
    user_data: UpdateUserRequest,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """更新用户信息"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 不允许修改自己的角色
    if user.id == current_user.id and user_data.role and user_data.role != user.role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能修改自己的角色",
        )

    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    logger.info(f"管理员 {current_user.username} 更新了用户 {user.username}")
    return {"message": "用户更新成功"}


@router.delete("/{user_id}", summary="删除用户（软删除）")
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """软删除用户（设置 is_active=False）"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.is_active = False
    await db.commit()
    logger.info(f"管理员 {current_user.username} 禁用了用户 {user.username}")
    return {"message": "用户已禁用"}


@router.put("/{user_id}/toggle-active", summary="启用/禁用用户")
async def toggle_user_active(
    user_id: int,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """切换用户启用/禁用状态"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能切换自己的状态",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    user.is_active = not user.is_active
    await db.commit()
    status_text = "启用" if user.is_active else "禁用"
    logger.info(f"管理员 {current_user.username} {status_text}了用户 {user.username}")
    return {"message": f"用户已{status_text}", "is_active": user.is_active}


@router.put("/{user_id}/reset-password", summary="重置密码")
async def reset_user_password(
    user_id: int,
    data: ResetPasswordRequest,
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """管理员重置用户密码"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 验证密码强度
    valid_pw, pw_errors = validate_password_strength(data.password)
    if not valid_pw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码不符合安全要求: {'; '.join(pw_errors)}",
        )

    user.password_hash = JWTHandler.hash_password(data.password)
    user.token_version += 1  # 使旧 token 失效
    await db.commit()
    logger.info(f"管理员 {current_user.username} 重置了用户 {user.username} 的密码")
    return {"message": "密码重置成功"}


@router.post("/{user_id}/avatar", summary="上传用户头像")
async def upload_user_avatar(
    user_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("users:manage")),
    db: AsyncSession = Depends(get_db),
):
    """上传用户头像（仅管理员）"""
    # 校验文件扩展名
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件类型，仅支持: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 读取文件内容并校验大小
    contents = await file.read()
    if len(contents) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="头像文件大小不能超过 2MB",
        )

    # 查找用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    # 删除旧头像文件
    if user.avatar:
        old_path = os.path.join(AVATAR_DIR, user.avatar)
        if os.path.isfile(old_path):
            os.remove(old_path)

    # 保存新头像
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(AVATAR_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    user.avatar = filename
    await db.commit()
    logger.info(f"管理员 {current_user.username} 更新了用户 {user.username} 的头像")
    return {"message": "头像上传成功", "avatar": f"/uploads/avatars/{filename}"}