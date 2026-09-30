"""
知识库文档模型
管理知识库文档的元数据信息
"""
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime
from .base import BaseModel


class KnowledgeDoc(BaseModel):
    """知识库文档元数据表"""

    __tablename__ = "knowledge_docs"

    title: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="文档标题"
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="分类"
    )
    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="文件路径"
    )
    file_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="文件类型"
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="文件大小(字节)"
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="分块数量"
    )
    is_indexed: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已索引"
    )
    uploaded_by: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, comment="上传者ID"
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, comment="版本号"
    )
    previous_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_docs.id"), nullable=True, comment="上一版本ID"
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已归档"
    )
    source_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="来源URL"
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="最后从来源获取时间"
    )
    is_stale: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="内容是否可能过时"
    )