"""
系统设置 API 路由
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from models.system_setting import SystemSetting
from auth.middleware import get_current_user, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["系统设置"])

# 默认设置
DEFAULT_SETTINGS = {
    "cashier_review_enabled": {"value": "true", "description": "是否启用出纳复核功能"},
}


class SettingUpdate(BaseModel):
    """设置更新请求体"""
    value: str


class SettingResponse(BaseModel):
    """设置响应体"""
    key: str
    value: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


async def _ensure_defaults(db: AsyncSession):
    """确保默认设置存在"""
    for key, info in DEFAULT_SETTINGS.items():
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        if not result.scalar_one_or_none():
            db.add(SystemSetting(key=key, value=info["value"], description=info["description"]))
    await db.commit()


@router.get("", response_model=list[SettingResponse], summary="获取所有系统设置")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取所有系统设置（管理员可查看全部，普通用户仅查看公开设置）"""
    await _ensure_defaults(db)
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
    settings = result.scalars().all()
    return settings


@router.get("/{key}", summary="获取单个系统设置")
async def get_setting(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定系统设置"""
    await _ensure_defaults(db)
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"设置 '{key}' 不存在")
    return {"key": setting.key, "value": setting.value, "description": setting.description}


@router.put("/{key}", summary="更新系统设置")
async def update_setting(
    key: str,
    data: SettingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("admin")),
):
    """更新指定系统设置（需要管理员权限）"""
    await _ensure_defaults(db)
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"设置 '{key}' 不存在")

    setting.value = data.value
    await db.commit()
    logger.info(f"系统设置已更新: {key} = {data.value}")
    return {"key": setting.key, "value": setting.value, "description": setting.description}