"""
模型路由服务
根据用户配置和偏好，智能选择 AI 模型（本地 Ollama 或外部 API）
"""
import logging
from typing import Optional, Dict, Any, List

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from config.settings import settings
from config.providers import DEFAULT_PROVIDERS
from services.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)


class ModelRouter:
    """AI 模型路由器，管理本地和外部模型的调度"""

    def __init__(self, db: AsyncSession, api_key_service: ApiKeyService):
        self.db = db
        self.api_key_service = api_key_service

    async def get_llm(
        self,
        user_id: int,
        model_preference: str = "auto",
        provider_code: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.1,
    ):
        """
        根据用户偏好获取 LLM 实例

        Args:
            user_id: 用户ID
            model_preference: 模型偏好 (auto/ollama/external)
            provider_code: 外部提供商代码
            model_name: 模型名称
            temperature: 温度参数

        Returns:
            ChatOllama 或 ChatOpenAI 实例
        """
        if model_preference == "ollama":
            # 强制使用本地 Ollama
            return await self._get_ollama_llm(model_name, temperature)

        if model_preference == "external":
            # 强制使用外部 API
            if not provider_code:
                raise ValueError("使用外部模型时必须指定 provider_code")
            return await self._get_external_llm(user_id, provider_code, model_name, temperature)

        # model_preference == "auto": 优先外部，无 Key 则 fallback 到 Ollama
        try:
            return await self._get_external_llm(user_id, provider_code, model_name, temperature)
        except ValueError:
            logger.info("无可用外部 API Key，回退到本地 Ollama")
            return await self._get_ollama_llm(model_name, temperature)

    async def _get_ollama_llm(self, model_name: Optional[str] = None, temperature: float = 0.1):
        """获取本地 Ollama LLM 实例"""
        model = model_name or "qwen2.5:7b"  # 默认模型

        # 拒绝 embedding/非聊天模型（防止用户通过 API 直接传入）
        _EMBEDDING_KEYWORDS = [
            "embed", "bge", "nomic", "stella", "e5-", "gte-",
            "clip", "blip", "vision", "ocr", "paraphrase",
            "all-minilm", "all-mpnet", "multilingual-e5",
        ]
        model_lower = model.lower()
        if any(kw in model_lower for kw in _EMBEDDING_KEYWORDS):
            logger.warning(f"拒绝使用非聊天模型: {model}，回退到默认模型")
            model = "qwen2.5:7b"

        logger.info(f"使用本地 Ollama 模型: {model}")
        return ChatOllama(
            model=model,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
        )

    async def _get_external_llm(
        self,
        user_id: int,
        provider_code: Optional[str],
        model_name: Optional[str],
        temperature: float,
    ):
        """获取外部 API LLM 实例"""
        # 获取用户活跃的 API Key
        api_key = await self.api_key_service.get_active_key(
            user_id, provider_code=provider_code
        )

        # 获取提供商配置
        if provider_code:
            provider_info = next(
                (p for p in DEFAULT_PROVIDERS if p["provider_code"] == provider_code),
                None,
            )
            if provider_info is None:
                raise ValueError(f"未知的提供商: {provider_code}")
        else:
            # 从用户的默认 Key 推断提供商
            provider_info = None

        if provider_info is None or not provider_info.get("base_url"):
            raise ValueError("无法确定外部 API 的 base_url")

        model = model_name or provider_info.get("default_model", "gpt-4o-mini")
        logger.info(f"使用外部模型: {provider_info['name']}/{model}")

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=provider_info["base_url"],
            temperature=temperature,
        )

    async def get_available_models(self, user_id: int) -> Dict[str, Any]:
        """获取可用模型列表"""
        result = {
            "local": [],
            "external": [],
        }

        # 获取本地 Ollama 模型列表（排除 embedding/视觉等非聊天模型）
        _EMBEDDING_PATTERNS = [
            "embed", "bge", "nomic", "stella", "e5-", "gte-",
            "clip", "blip", "vision", "ocr", "paraphrase",
            "all-minilm", "all-mpnet", "multilingual-e5",
        ]
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    local_models = []
                    for m in data.get("models", []):
                        name_lower = m["name"].lower()
                        # 过滤掉 embedding 模型（名称包含 embed/bge/nomic 等关键词）
                        if any(p in name_lower for p in _EMBEDDING_PATTERNS):
                            logger.debug(f"跳过非聊天模型: {m['name']}")
                            continue
                        local_models.append({"name": m["name"], "provider": "Ollama"})
                    result["local"] = local_models
        except Exception as e:
            logger.warning(f"获取本地模型列表失败: {e}")
            result["local"] = []

        # 获取用户配置的外部模型
        try:
            keys = await self.api_key_service.list_keys(user_id)
            active_keys = [k for k in keys if k["is_active"]]
            external_providers = set()
            for k in active_keys:
                provider_code = k["provider_code"]
                if provider_code in external_providers:
                    continue
                external_providers.add(provider_code)

                provider_info = next(
                    (p for p in DEFAULT_PROVIDERS if p["provider_code"] == provider_code),
                    None,
                )
                if provider_info:
                    for model_name in provider_info.get("models", []):
                        result["external"].append({
                            "name": model_name,
                            "provider": provider_info["name"],
                            "provider_code": provider_code,
                        })
        except Exception as e:
            logger.warning(f"获取外部模型列表失败: {e}")

        return result