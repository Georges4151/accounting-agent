"""
JWT 令牌处理模块
负责生成和验证 JWT 访问令牌和刷新令牌
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import logging

from jose import jwt, JWTError
import bcrypt

from config.settings import settings

logger = logging.getLogger(__name__)


class JWTHandler:
    """JWT 处理器，提供令牌生成、验证和密码哈希功能"""

    @staticmethod
    def create_access_token(user_id: int, role: str, username: str = "", token_version: int = 1) -> str:
        """创建访问令牌"""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_EXPIRE_MINUTES
        )
        payload = {
            "sub": str(user_id),
            "role": role,
            "username": username,
            "type": "access",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "ver": token_version,
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")

    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        """创建刷新令牌"""
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_REFRESH_EXPIRE_MINUTES
        )
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, settings.JWT_REFRESH_SECRET_KEY, algorithm="HS256")

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """验证令牌并返回 payload"""
        secret_key = (
            settings.JWT_SECRET_KEY
            if token_type == "access"
            else settings.JWT_REFRESH_SECRET_KEY
        )
        try:
            payload = jwt.decode(token, secret_key, algorithms=["HS256"])
            if payload.get("type") != token_type:
                raise JWTError("Token type mismatch")
            return payload
        except JWTError as e:
            logger.warning(f"令牌验证失败: {e}")
            raise

    @staticmethod
    def hash_password(password: str) -> str:
        """使用 bcrypt 对密码进行哈希"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """验证密码是否匹配哈希值"""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))