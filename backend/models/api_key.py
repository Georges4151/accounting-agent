"""
API Key 相关模型
包含 AI 提供商、用户 API Key 和使用日志
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Boolean, Integer, BigInteger, Text, DateTime, ForeignKey, Numeric, func,
)
from .base import BaseModel


class ApiProvider(BaseModel):
    """AI 模型提供商表"""

    __tablename__ = "api_providers"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="提供商名称"
    )
    provider_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="提供商代码"
    )
    base_url: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="API基础URL"
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Logo URL"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="描述"
    )


class UserApiKey(BaseModel):
    """用户 API Key 表"""

    __tablename__ = "user_api_keys"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID"
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("api_providers.id", ondelete="CASCADE"), nullable=False, comment="提供商ID"
    )
    key_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Key名称"
    )
    encrypted_key: Mapped[str] = mapped_column(
        Text, nullable=False, comment="加密后的API Key"
    )
    key_prefix: Mapped[str] = mapped_column(
        String(8), nullable=False, comment="Key前缀脱敏显示"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否默认Key"
    )
    total_calls: Mapped[int] = mapped_column(
        BigInteger, default=0, comment="总调用次数"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后使用时间"
    )
    balance: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 4), nullable=True, comment="余额"
    )

    # 关联关系
    provider: Mapped["ApiProvider"] = relationship("ApiProvider", lazy="selectin")


class ApiKeyUsageLog(BaseModel):
    """API Key 使用日志表"""

    __tablename__ = "api_key_usage_logs"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID"
    )
    api_key_id: Mapped[int] = mapped_column(
        ForeignKey("user_api_keys.id", ondelete="SET NULL"), nullable=True, comment="API Key ID"
    )
    provider_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="提供商名称"
    )
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="模型名称"
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer, default=0, comment="消耗Token数"
    )
    cost_estimated: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 6), nullable=True, comment="预估费用"
    )