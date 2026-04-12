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

# ---------------------------------------------------------------------------
# LLM：默认对接「硅基流动 SiliconFlow」（OpenAI 兼容 Chat Completions）
# API Key 请填在环境变量或项目根目录 .env 中，见 README「环境变量」。
# ---------------------------------------------------------------------------
# 硅基流动控制台申请的 sk-... Key（推荐只填这个）
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "").strip()
# 兼容：若仍使用 OPENAI_API_KEY 命名也可
_OPENAI_API_KEY_FALLBACK = os.getenv("OPENAI_API_KEY", "").strip()
# 供 app/utils/llm.py 使用的「最终生效」Key：硅基流动优先
OPENAI_API_KEY = SILICONFLOW_API_KEY or _OPENAI_API_KEY_FALLBACK

# 硅基流动 OpenAI 兼容 Base URL（必须含 /v1）
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.siliconflow.cn/v1")
# 模型 ID：优先 .env 中的 SILICONFLOW_MODEL，其次 OPENAI_MODEL，最后为下方默认
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "").strip()
_OPENAI_MODEL_ENV = os.getenv("OPENAI_MODEL", "").strip()
_DEFAULT_SILICONFLOW_MODEL = "Qwen/Qwen3.5-35B-A3B"
OPENAI_MODEL = SILICONFLOW_MODEL or _OPENAI_MODEL_ENV or _DEFAULT_SILICONFLOW_MODEL

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_TIMEOUT_SEC = float(os.getenv("LLM_TIMEOUT_SEC", "120"))

# Prompt 模板目录
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(filename: str) -> str:
    """从 app/prompts/ 加载提示词文本。"""
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")
