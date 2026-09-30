"""
API Key 管理服务
提供 API Key 的增删改查和默认设置
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.api_key import UserApiKey, ApiProvider
from services.key_encryption import KeyEncryptionService

logger = logging.getLogger(__name__)


class ApiKeyService:
    """API Key 业务逻辑服务"""

    def __init__(self, db: AsyncSession, enc_service: KeyEncryptionService):
        self.db = db
        self.enc = enc_service

    async def _get_user_key(self, user_id: int, key_id: int) -> UserApiKey:
        """获取用户的指定 Key，不存在则抛出异常"""
        result = await self.db.execute(
            select(UserApiKey).where(
                UserApiKey.id == key_id,
                UserApiKey.user_id == user_id,
            )
        )
        key = result.scalar_one_or_none()
        if key is None:
            raise ValueError(f"API Key (id={key_id}) 不存在")
        return key

    async def _get_provider(self, provider_code: str) -> ApiProvider:
        """获取或创建提供商"""
        result = await self.db.execute(
            select(ApiProvider).where(ApiProvider.provider_code == provider_code)
        )
        provider = result.scalar_one_or_none()
        if provider is None:
            # 尝试从配置中获取提供商信息
            from config.providers import DEFAULT_PROVIDERS
            provider_info = next(
                (p for p in DEFAULT_PROVIDERS if p["provider_code"] == provider_code),
                None,
            )
            if provider_info is None:
                raise ValueError(f"未知的提供商: {provider_code}")

            provider = ApiProvider(
                name=provider_info["name"],
                provider_code=provider_info["provider_code"],
                base_url=provider_info["base_url"],
            )
            self.db.add(provider)
            await self.db.flush()
        return provider

    async def add_key(
        self, user_id: int, provider_code: str, api_key: str, key_name: str
    ) -> UserApiKey:
        """添加 API Key（加密存储）"""
        provider = await self._get_provider(provider_code)

        # 加密 API Key
        encrypted = self.enc.encrypt(api_key)
        key_prefix = self.enc.get_key_prefix(api_key)

        # 如果这是用户第一个 Key，自动设为默认
        result = await self.db.execute(
            select(UserApiKey).where(UserApiKey.user_id == user_id)
        )
        existing_keys = result.scalars().all()
        is_first = len(existing_keys) == 0

        user_key = UserApiKey(
            user_id=user_id,
            provider_id=provider.id,
            key_name=key_name,
            encrypted_key=encrypted,
            key_prefix=key_prefix,
            is_default=is_first,
        )
        self.db.add(user_key)
        await self.db.commit()
        await self.db.refresh(user_key)
        return user_key

    async def list_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """列出用户的所有 API Key（不返回原始 Key）"""
        result = await self.db.execute(
            select(UserApiKey)
            .where(UserApiKey.user_id == user_id)
            .order_by(UserApiKey.created_at.desc())
        )
        keys = result.scalars().all()

        items = []
        for key in keys:
            # 获取提供商名称
            provider_result = await self.db.execute(
                select(ApiProvider).where(ApiProvider.id == key.provider_id)
            )
            provider = provider_result.scalar_one_or_none()

            items.append({
                "id": key.id,
                "alias": key.key_name,
                "provider_code": provider.provider_code if provider else "",
                "provider_name": provider.name if provider else "",
                "api_key_preview": key.key_prefix,
                "is_active": key.is_active,
                "is_default": key.is_default,
                "call_count": key.total_calls,
                "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
                "created_at": key.created_at.isoformat() if key.created_at else None,
            })
        return items

    async def set_default(self, user_id: int, key_id: int) -> None:
        """将指定 Key 设为默认"""
        key = await self._get_user_key(user_id, key_id)

        # 取消其他 Key 的默认状态
        await self.db.execute(
            update(UserApiKey)
            .where(UserApiKey.user_id == user_id)
            .values(is_default=False)
        )

        # 设置当前 Key 为默认
        key.is_default = True
        await self.db.commit()

    async def toggle_active(self, user_id: int, key_id: int) -> Dict[str, Any]:
        """切换 Key 的启用/禁用状态"""
        key = await self._get_user_key(user_id, key_id)
        key.is_active = not key.is_active
        await self.db.commit()
        return {
            "message": "Key 已启用" if key.is_active else "Key 已禁用",
            "is_active": key.is_active,
        }

    async def delete_key(self, user_id: int, key_id: int) -> None:
        """删除 API Key"""
        key = await self._get_user_key(user_id, key_id)
        await self.db.delete(key)
        await self.db.commit()

    async def get_active_key(
        self, user_id: int, provider_code: Optional[str] = None
    ) -> str:
        """获取用户的活跃 API Key（解密后）"""
        query = select(UserApiKey).where(
            UserApiKey.user_id == user_id,
            UserApiKey.is_active == True,
        )

        if provider_code:
            # 按提供商筛选
            provider_result = await self.db.execute(
                select(ApiProvider).where(ApiProvider.provider_code == provider_code)
            )
            provider = provider_result.scalar_one_or_none()
            if provider is None:
                raise ValueError(f"提供商 {provider_code} 不存在")
            query = query.where(UserApiKey.provider_id == provider.id)

        query = query.order_by(UserApiKey.is_default.desc())
        result = await self.db.execute(query)
        key = result.scalars().first()

        if key is None:
            detail = f"提供商 {provider_code}" if provider_code else "任何提供商"
            raise ValueError(f"未找到 {detail} 的活跃 API Key")

        # 解密并返回
        return self.enc.decrypt(key.encrypted_key)