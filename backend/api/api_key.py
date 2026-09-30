"""
API Key 管理 API 路由
管理用户的外部 AI 模型 API Key
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from database import get_db
from models.user import User
from auth.middleware import get_current_user
from services.key_encryption import KeyEncryptionService
from services.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/api-keys", tags=["API Key管理"])


# ========== 请求/响应模型 ==========

class AddKeyRequest(BaseModel):
    """添加 API Key 请求体"""
    provider_code: str = Field(..., description="提供商代码")
    api_key: str = Field(..., min_length=1, description="API Key")
    alias: Optional[str] = Field(None, max_length=100, description="Key别名")
    base_url: Optional[str] = Field(None, description="自定义API地址")


class KeyListItem(BaseModel):
    """Key 列表项"""
    id: int
    alias: str
    provider_code: str
    provider_name: str
    api_key_preview: str
    is_active: bool
    is_default: bool
    call_count: int
    last_used_at: str | None
    created_at: str | None

    class Config:
        from_attributes = True


# ========== API 端点 ==========

@router.get("", summary="获取用户的所有 API Key")
async def list_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有 API Key（不返回原始 Key）"""
    service = ApiKeyService(db, KeyEncryptionService())
    keys = await service.list_keys(current_user.id)
    return {"keys": keys}


@router.post("", summary="添加 API Key")
async def add_key(
    key_data: AddKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加新的 API Key（加密存储）"""
    enc_service = KeyEncryptionService()
    # 校验 Key 格式
    if not enc_service.validate_key_format(key_data.api_key, key_data.provider_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API Key 格式不正确",
        )

    service = ApiKeyService(db, enc_service)
    try:
        user_key = await service.add_key(
            current_user.id,
            key_data.provider_code,
            key_data.api_key,
            key_data.alias or key_data.provider_code,
        )
        logger.info(f"用户 {current_user.username} 添加了 {key_data.provider_code} 的 API Key")
        return {"message": "API Key 添加成功", "id": user_key.id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{key_id}/default", summary="设为默认 Key")
async def set_default_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """将指定 Key 设为默认"""
    service = ApiKeyService(db, KeyEncryptionService())
    try:
        await service.set_default(current_user.id, key_id)
        return {"message": "已设为默认"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.put("/{key_id}/toggle", summary="启用/禁用 Key")
async def toggle_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切换 API Key 的启用/禁用状态"""
    service = ApiKeyService(db, KeyEncryptionService())
    try:
        result = await service.toggle_active(current_user.id, key_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{key_id}", summary="删除 API Key")
async def delete_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定的 API Key"""
    service = ApiKeyService(db, KeyEncryptionService())
    try:
        await service.delete_key(current_user.id, key_id)
        logger.info(f"用户 {current_user.username} 删除了 API Key (id={key_id})")
        return {"message": "API Key 已删除"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/providers", summary="获取支持的提供商列表")
async def get_providers(
    _: User = Depends(get_current_user),
):
    """获取系统支持的 AI 模型提供商列表"""
    from config.providers import DEFAULT_PROVIDERS
    # 转换为前端期望的格式
    frontend_providers = []
    for p in DEFAULT_PROVIDERS:
        frontend_providers.append({
            "code": p["provider_code"],
            "name": p["name"],
            "get_link": p.get("key_guide", ""),
            "base_url": p.get("base_url", ""),
            "default_model": p.get("default_model", ""),
            "models": p.get("models", []),
        })
    return {"providers": frontend_providers}