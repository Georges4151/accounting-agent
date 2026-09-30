"""
API Key 加密服务
使用 Fernet 对称加密保护 API Key 的存储安全
"""
import os
import logging
from cryptography.fernet import Fernet

from config.settings import settings

logger = logging.getLogger(__name__)


class KeyEncryptionService:
    """API Key 加密和解密服务"""

    def __init__(self):
        """初始化加密密钥，从环境变量获取或自动生成"""
        key = settings.KEY_ENCRYPTION_KEY

        if not key or key == "your-fernet-key-change-in-production":
            # 如果未配置密钥，生成一个并警告
            key = Fernet.generate_key().decode()
            logger.warning(
                "⚠️  未配置 KEY_ENCRYPTION_KEY，已自动生成临时密钥。"
                "请将以下密钥添加到 .env 文件中以确保重启后数据可解密:\n"
                f"KEY_ENCRYPTION_KEY={key}"
            )

        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            logger.error(f"加密密钥格式无效: {e}")
            raise ValueError(f"KEY_ENCRYPTION_KEY 格式无效: {e}")

    def encrypt(self, api_key: str) -> str:
        """加密 API Key"""
        try:
            encrypted = self._fernet.encrypt(api_key.encode("utf-8"))
            return encrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"加密 API Key 失败: {e}")
            raise ValueError(f"加密失败: {e}")

    def decrypt(self, encrypted_key: str) -> str:
        """解密 API Key"""
        try:
            decrypted = self._fernet.decrypt(encrypted_key.encode("utf-8"))
            return decrypted.decode("utf-8")
        except Exception as e:
            logger.error(f"解密 API Key 失败: {e}")
            raise ValueError(f"解密失败，密钥可能已变更: {e}")

    @staticmethod
    def get_key_prefix(api_key: str) -> str:
        """返回 API Key 的脱敏前缀（如 sk-****）"""
        if len(api_key) <= 8:
            return api_key[:4] + "****"
        return api_key[:4] + "****" + api_key[-4:]

    @staticmethod
    def validate_key_format(api_key: str, provider_code: str) -> bool:
        """校验 API Key 格式是否合法"""
        if not api_key or len(api_key.strip()) < 8:
            return False
        # 基本校验：只检查非空和长度
        return True