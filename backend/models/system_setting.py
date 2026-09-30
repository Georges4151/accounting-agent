"""
系统设置模型
存储全局系统配置（键值对）
"""
from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class SystemSetting(BaseModel):
    """系统设置表"""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="设置键名"
    )
    value: Mapped[str] = mapped_column(
        Text, nullable=False, default="", comment="设置值（JSON字符串）"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="设置说明"
    )