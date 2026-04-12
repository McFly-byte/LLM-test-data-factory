"""generate_knowledge 节点：为当前主题批次生成知识条目。"""

from __future__ import annotations

import json
import logging
import random
import uuid
from typing import Any

from app import config
from app.state import FactoryState, KnowledgeItem, TopicPlan
from app.utils.json_parser import JSONParseError, parse_json_array
from app.utils.llm import LLMClient

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
    template = config.load_prompt("generate_knowledge.txt")
    prompt = (
        template.replace("<<TOPIC_PLAN_JSON>>", json.dumps(plan, ensure_ascii=False))
        .replace("<<BATCH_MIN>>", str(batch_min))
        .replace("<<BATCH_MAX>>", str(batch_max))
    )

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
            new_items.append(
                KnowledgeItem(
                    kid=kid,
                    topic=plan["topic"],
                    subtopic=subtopic,
                    title=title,
                    content=content,
                    keywords=keywords[:12],
                )
            )
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
