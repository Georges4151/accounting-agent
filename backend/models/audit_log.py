"""
审计日志模型
记录系统中的关键操作
"""
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, ForeignKey
from .base import BaseModel


class AuditLog(BaseModel):
    """审计日志表"""

    __tablename__ = "audit_logs"

    user_id: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="用户ID"
    )
    username: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="用户名"
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="操作类型"
    )
    resource: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="操作资源"
    )
    detail: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="操作详情"
    )
    ip_address: Mapped[str] = mapped_column(
        String(45), nullable=False, comment="IP地址"
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="用户代理"
    )
    status: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="操作结果: success/failure"
    )
    operation_category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="操作分类: voucher/create, user/login 等"
    )
    affected_resource_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="受影响的资源ID"
    )
    request_body: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="请求体（截断到1000字符）"
    )
    response_status: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="HTTP 响应状态码"
    )

    # 关联字段变更记录
    field_changes: Mapped[list["AuditFieldChange"]] = relationship(
        "AuditFieldChange",
        back_populates="audit_log",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class AuditFieldChange(BaseModel):
    """审计字段变更记录表"""

    __tablename__ = "audit_field_changes"

    audit_log_id: Mapped[int] = mapped_column(
        ForeignKey("audit_logs.id", ondelete="CASCADE"),
        nullable=False, comment="关联的审计日志ID"
    )
    field_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="字段名"
    )
    field_label: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="字段显示名"
    )
    old_value: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="旧值"
    )
    new_value: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="新值"
    )

    # 关联审计日志
    audit_log: Mapped["AuditLog"] = relationship(
        "AuditLog",
        back_populates="field_changes",
    )