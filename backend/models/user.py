"""
用户模型
定义系统用户的数据表结构
"""
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, DateTime, Integer
from .base import BaseModel


class User(BaseModel):
    """用户表"""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="用户名"
    )
    real_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="真实姓名"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希"
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="角色: admin/accountant/cashier/reviewer/viewer"
    )
    department: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="部门"
    )
    email: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="邮箱"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后登录时间"
    )
    login_ip: Mapped[str | None] = mapped_column(
        String(45), nullable=True, comment="最后登录IP"
    )
    login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, comment="连续登录失败次数"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="账户锁定截止时间"
    )
    two_factor_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否启用双因素认证"
    )
    totp_secret: Mapped[str | None] = mapped_column(
        String(32), nullable=True, comment="TOTP密钥"
    )
    token_version: Mapped[int] = mapped_column(
        Integer, default=1, comment="Token版本号，用于强制登出"
    )
    avatar: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="头像文件路径"
    )