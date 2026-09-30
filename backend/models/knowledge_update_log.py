"""
知识库更新日志模型
记录知识库自动更新的历史和状态
"""
from sqlalchemy import String, Text, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from models.base import BaseModel


class KnowledgeUpdateLog(BaseModel):
    """知识库更新日志表"""

    __tablename__ = "knowledge_update_logs"

    source_url: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="来源URL"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="状态: success/failed/pending"
    )
    new_docs_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="新增文档数"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="错误信息"
    )