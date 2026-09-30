"""
归档密钥模型 — USB 密钥文件验证
用于账套归档等敏感操作的安全验证
"""
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ArchiveKey(Base):
    """
    归档密钥
    存储密钥的 SHA-256 哈希值，用于验证用户上传的密钥文件
    """
    __tablename__ = "archive_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, comment="密钥 SHA-256 哈希"
    )
    usb_serial_hash: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="绑定的 U 盘序列号 SHA-256 哈希"
    )
    key_label: Mapped[str] = mapped_column(
        String(100), default="默认密钥", comment="密钥标签"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="创建者用户ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="创建时间"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后使用时间"
    )