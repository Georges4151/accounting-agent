"""
AI 模型提供商配置
定义系统支持的第三方 AI 模型提供商列表
"""
from typing import List, Dict, Any

# 默认支持的第三方 AI 模型提供商
DEFAULT_PROVIDERS: List[Dict[str, Any]] = [
    {
        "provider_code": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "key_guide": "https://platform.deepseek.com/api_keys",
    },
    {
        "provider_code": "qwen",
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": ["qwen-plus", "qwen-max", "qwen-turbo"],
        "key_guide": "https://dashscope.console.aliyun.com/apiKey",
    },
    {
        "provider_code": "zhipu",
        "name": "智谱清言",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "models": ["glm-4-plus", "glm-4-flash"],
        "key_guide": "https://open.bigmodel.cn/usercenter/apikeys",
    },
    {
        "provider_code": "moonshot",
        "name": "Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "key_guide": "https://platform.moonshot.cn/console/api-keys",
    },
    {
        "provider_code": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "key_guide": "https://platform.openai.com/api-keys",
    },
    {
        "provider_code": "custom",
        "name": "自定义",
        "base_url": "",
        "default_model": "",
        "models": [],
        "key_guide": "",
    },
]