"""plan_topics 节点：根据领域规划 8~10 个主题桶。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app import config
from app.state import FactoryState, TopicPlan
from app.utils.json_parser import JSONParseError, parse_json_array
from app.utils.llm import LLMClient
from app.utils.progress import format_factory_snapshot

logger = logging.getLogger(__name__)


def plan_topics(state: FactoryState, llm: LLMClient | None = None) -> dict[str, Any]:
    """
    调用 LLM 生成主题规划。
    若已存在 topic_plans（非空），则跳过，避免重复规划。
    """
    if state.get("topic_plans"):
        logger.info("[plan_topics] 已存在主题规划，跳过。| %s", format_factory_snapshot(state))
        return {}

    logger.info(
        "[plan_topics] 调用模型规划主题… | domain前80字=%s | %s",
        (state.get("domain", config.DEFAULT_DOMAIN) or "")[:80],
        format_factory_snapshot(state),
    )
    client = llm or LLMClient()
    template = config.load_prompt("plan_topics.txt")
    prompt = template.replace("<<DOMAIN>>", state.get("domain", config.DEFAULT_DOMAIN))

    try:
        raw = client.complete(prompt, temperature=0.35)
        arr = parse_json_array(raw)
    except (JSONParseError, Exception) as e:  # noqa: BLE001
        logger.exception("[plan_topics] 规划失败，将使用内置兜底主题：%s", e)
        fb = _fallback_plans(state.get("domain", ""))
        logger.info("[plan_topics] 兜底主题数：%s", len(fb))
        return {"topic_plans": fb}

    plans: list[TopicPlan] = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        try:
            plans.append(
                TopicPlan(
                    topic=str(item["topic"]),
                    subtopics=[str(x) for x in item.get("subtopics", [])],
                    target_knowledge_count=int(item.get("target_knowledge_count", 20)),
                    target_qa_count=int(item.get("target_qa_count", 30)),
                )
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("[plan_topics] 跳过无效主题项：%s | data=%s", e, item)

    if len(plans) < 8:
        logger.warning("[plan_topics] 主题数量不足 8，将用兜底补齐。")
        plans = _merge_with_fallback(plans, state.get("domain", ""))

    top_names = [p["topic"] for p in plans[:10]]
    logger.info("[plan_topics] 模型规划完成 | 主题数=%s | 预览=%s", len(plans[:10]), top_names[:5])
    return {"topic_plans": plans[:10]}


def _fallback_plans(domain: str) -> list[TopicPlan]:
    _ = domain
    return _merge_with_fallback([], "")


def _merge_with_fallback(existing: list[TopicPlan], domain: str) -> list[TopicPlan]:
    _ = domain
    base = [
        TopicPlan(
            topic="RAG 基础与变体",
            subtopics=["稀疏检索与稠密检索", "上下文窗口与噪声", "引用与可追溯性"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="文档解析与 Chunking",
            subtopics=["结构感知切分", "重叠策略", "表格与代码块处理"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="Embedding 与向量检索",
            subtopics=["向量归一化", "相似度度量", "ANN 参数与召回"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="检索增强与重排",
            subtopics=["混合检索融合", "rerank 成本", "两阶段检索"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="Agent 与工具调用",
            subtopics=["Function Calling 约束", "工具失败重试", "并行工具调用"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="LangGraph 与编排",
            subtopics=["状态图设计", "条件边与循环", "人机协同中断"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="生态框架对比与实践",
            subtopics=["LangChain 模块化", "LlamaIndex 索引抽象", "AutoGen 多代理边界", "MCP 工具协议"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="可观测性与评测",
            subtopics=["LangSmith Trace", "离线评测集", "回归对比实验"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="安全、幻觉与对抗输入",
            subtopics=["Prompt Injection", "数据外泄风险", "幻觉缓解策略"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
        TopicPlan(
            topic="故障诊断与最佳实践",
            subtopics=["检索为空排查", "延迟与成本", "线上监控指标"],
            target_knowledge_count=25,
            target_qa_count=35,
        ),
    ]
    merged = {json.dumps(p, sort_keys=True, ensure_ascii=False): p for p in existing}
    out = list(existing)
    for p in base:
        key = json.dumps(p, sort_keys=True, ensure_ascii=False)
        if key not in merged:
            out.append(p)
            merged[key] = p
        if len(out) >= 10:
            break
    return out[:10]
