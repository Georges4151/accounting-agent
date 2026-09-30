"""
Agent 基类
所有专业 Agent 的抽象基类，使用 LangGraph 构建 Agent
"""
from typing import List, Optional, Any, Callable
from langgraph.prebuilt import create_react_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool


class BaseAgent:
    """Agent 基类，提供 LLM 和工具集成的基础框架"""

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Optional[List[BaseTool]] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        初始化 Agent

        Args:
            llm: LangChain 聊天模型实例
            tools: Agent 可用的工具列表
            system_prompt: 系统提示词
        """
        self.llm = llm
        self.tools = tools or []
        self.system_prompt = system_prompt or "你是一个专业的财务助手。"
        self._agent = None

    def create_agent(self):
        """
        使用 LangGraph 创建 ReAct Agent

        Returns:
            配置好的 LangGraph Agent
        """
        if self._agent is None:
            self._agent = create_react_agent(
                model=self.llm,
                tools=self.tools,
                state_modifier=self.system_prompt,
            )
        return self._agent

    async def run(self, message: str) -> str:
        """
        运行 Agent 处理用户消息

        Args:
            message: 用户输入消息

        Returns:
            Agent 的响应文本
        """
        agent = self.create_agent()
        try:
            result = await agent.ainvoke({"messages": [("user", message)]})
            # 提取最后一条 AI 消息
            messages = result.get("messages", [])
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.type == "ai":
                    return msg.content
            return "无法获取 Agent 响应"
        except Exception as e:
            return f"Agent 执行出错: {str(e)}"