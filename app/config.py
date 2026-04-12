"""全局配置：默认值与环境变量映射。"""

from __future__ import annotations

import os
from pathlib import Path

# 项目根目录（含 app/ 与 outputs/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 默认领域描述（用于规划主题与生成语料）
DEFAULT_DOMAIN = (
    "面向 LLM 应用、Agent、RAG、LangGraph、LlamaIndex、LangSmith、MCP、LangChain、"
    "AutoGen、Prompt Injection、幻觉、安全、检索、重排、评测、追踪、故障诊断等方向的工程实践。"
)

# 生成与终止目标
TARGET_QA_COUNT = 200
TARGET_KNOWLEDGE_CHARS = 12_000
MAX_REVISION_ROUNDS = 2
DUPLICATE_THRESHOLD = 0.92

# 每批生成规模（可按需微调）
KNOWLEDGE_BATCH_MIN = 5
KNOWLEDGE_BATCH_MAX = 10
QA_BATCH_SIZE = 5

# LLM 相关环境变量
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_TIMEOUT_SEC = float(os.getenv("LLM_TIMEOUT_SEC", "120"))

# Prompt 模板目录
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(filename: str) -> str:
    """从 app/prompts/ 加载提示词文本。"""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")
