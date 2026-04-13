"""generate_knowledge 节点：为当前主题批次生成知识条目。"""

from __future__ import annotations

import json
import logging
import random
import uuid
from typing import Any, cast

from app import config
from app.state import FactoryState, KnowledgeItem, TopicPlan
from app.utils.json_parser import JSONParseError, parse_json_array
from app.utils.llm import LLMClient
from app.utils.web_search import hits_as_prompt_json, search_for_topic_plan

logger = logging.getLogger(__name__)


def generate_knowledge(state: FactoryState, llm: LLMClient | None = None) -> dict[str, Any]:
    """
    针对当前 topic plan 生成 5~10 条知识条目并追加到 knowledge_items。
    """
    plans = state.get("topic_plans") or []
    if not plans:
        logger.warning("[generate_knowledge] 无主题规划，跳过。")
        return {}

    idx = int(state.get("current_topic_index", 0)) % len(plans)
    plan: TopicPlan = plans[idx]

    batch_min = config.KNOWLEDGE_BATCH_MIN
    batch_max = config.KNOWLEDGE_BATCH_MAX
    batch_n = random.randint(batch_min, batch_max)

    client = llm or LLMClient()
    hits = search_for_topic_plan(plan)
    search_json = hits_as_prompt_json(hits)
    if hits:
        logger.info("[generate_knowledge] 已拉取外部检索 %s 条，用于增强知识生成", len(hits))
    else:
        logger.info("[generate_knowledge] 外部检索无结果或未启用，将按纯模型常识生成")

    template = config.load_prompt("generate_knowledge.txt")
    prompt = (
        template.replace("<<TOPIC_PLAN_JSON>>", json.dumps(plan, ensure_ascii=False))
        .replace("<<SEARCH_RESULTS_JSON>>", search_json)
        .replace("<<BATCH_MIN>>", str(batch_min))
        .replace("<<BATCH_MAX>>", str(batch_max))
    )

    allowed_urls = {h["url"] for h in hits}

    new_items: list[KnowledgeItem] = []
    try:
        raw = client.complete(prompt, temperature=0.45)
        arr = parse_json_array(raw)
    except (JSONParseError, Exception) as e:  # noqa: BLE001
        logger.exception("[generate_knowledge] 解析失败，本批次跳过：%s", e)
        return {"current_topic_index": (idx + 1) % len(plans)}

    for obj in arr:
        if not isinstance(obj, dict):
            continue
        try:
            title = str(obj["title"]).strip()
            subtopic = str(obj["subtopic"]).strip()
            keywords = [str(x).strip() for x in obj.get("keywords", []) if str(x).strip()]
            content = str(obj["content"]).strip()
            if not title or not content:
                continue
            kid = f"k-{uuid.uuid4().hex[:12]}"
            item: dict[str, Any] = {
                "kid": kid,
                "topic": plan["topic"],
                "subtopic": subtopic,
                "title": title,
                "content": content,
                "keywords": keywords[:12],
            }
            raw_sources = obj.get("sources", [])
            if isinstance(raw_sources, list) and allowed_urls:
                src = [str(x).strip() for x in raw_sources if str(x).strip() in allowed_urls]
                src = src[:3]
                if src:
                    item["sources"] = src
            new_items.append(cast(KnowledgeItem, item))
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("[generate_knowledge] 丢弃无效知识条目：%s | data=%s", e, obj)

    merged = list(state.get("knowledge_items", [])) + new_items
    logger.info(
        "[generate_knowledge] 主题=%s | 本批新增=%s | 累计知识条=%s",
        plan["topic"],
        len(new_items),
        len(merged),
    )
    return {
        "knowledge_items": merged,
        "current_topic_index": (idx + 1) % len(plans),
    }
