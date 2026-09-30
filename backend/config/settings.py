"""
应用配置模块
使用 pydantic-settings 从 .env 文件和系统环境变量加载配置
"""
from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    """应用全局配置"""

    # ========== 数据库 ==========
    DATABASE_URL: str

    # ========== JWT ==========
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_MINUTES: int = 10080  # 7天

    # ========== 加密 ==========
    KEY_ENCRYPTION_KEY: str

    # ========== Ollama ==========
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # ========== 发票识别 ==========
    INVOICE_VISION_MODEL: str = ""  # 为空时自动检测可用模型

    # ========== CORS ==========
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # ========== 安全 ==========
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 30
    PASSWORD_MIN_LENGTH: int = 8
    ENABLE_AMOUNT_MASKING: bool = True
    RATE_LIMIT_MAX_ATTEMPTS: int = 5
    RATE_LIMIT_WINDOW_MINUTES: int = 15
    ACCOUNT_LOCK_ATTEMPTS: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            """解析环境变量，支持 JSON 数组格式"""
            if field_name == "CORS_ORIGINS":
                try:
                    return json.loads(raw_val)
                except (json.JSONDecodeError, TypeError):
                    return [origin.strip() for origin in raw_val.split(",")]
            return raw_val


# 全局单例配置实例
settings = Settings()