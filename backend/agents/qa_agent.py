"""
问答 Agent
基于知识库回答企业财务制度问题
"""
import logging
from typing import List, Optional

from langchain_core.tools import tool
from langchain_core.language_models import BaseChatModel

from .base_agent import BaseAgent

logger = logging.getLogger(__name__)


class QAAgent(BaseAgent):
    """问答 Agent，基于知识库回答财务制度问题"""

    def __init__(self, llm: BaseChatModel, tools: Optional[List] = None):
        qa_tools = [search_knowledge_base]
        system_prompt = """你是一个企业财务制度顾问，负责回答公司内部财务制度相关问题。

你需要：
1. 根据用户的问题，使用 search_knowledge_base 工具检索相关制度文档
2. 基于检索到的制度内容给出准确回答
3. 如果知识库中没有相关内容，诚实地告知用户
4. 引用具体的制度文档名称和条款

请始终保持专业、准确的回答风格。"""
        super().__init__(llm=llm, tools=tools or qa_tools, system_prompt=system_prompt)


# ========== 问答工具函数 ==========

@tool
def search_knowledge_base(query: str) -> str:
    """检索知识库中的制度文档

    Args:
        query: 查询内容

    Returns:
        格式化后的检索结果文本
    """
    try:
        from services.rag_service import KnowledgeBaseService

        kb_service = KnowledgeBaseService()
        results = kb_service.search(query, top_k=5)

        if not results:
            return "知识库中未找到相关内容。请确保已上传相关制度文档。"

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"【文档{i}】来源: {r['filename']}\n"
                f"相关度: {r['score']:.2%}\n"
                f"内容: {r['content']}\n"
            )
        return "\n---\n".join(formatted)

    except Exception as e:
        error_msg = str(e)
        if "connection" in error_msg.lower() or "connect" in error_msg.lower():
            return (
                "知识库检索服务暂时不可用（Ollama 服务未连接）。"
                "请确保 Ollama 服务已启动并且 bge-m3 模型已安装。"
                "您可以通过运行 'ollama pull bge-m3' 安装该模型。"
            )
        logger.error(f"知识库检索失败: {e}")
        return f"知识库检索失败: {error_msg}"