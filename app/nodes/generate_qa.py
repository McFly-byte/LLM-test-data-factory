"""generate_qa 节点：基于抽样知识条目生成 QA 并进入待审核队列。"""

from __future__ import annotations

import json
import logging
import random
import uuid
from typing import Any

from app import config
from app.state import FactoryState, KnowledgeItem, QASample
from app.utils.json_parser import JSONParseError, parse_json_array
from app.utils.llm import LLMClient

logger = logging.getLogger(__name__)


def generate_qa(state: FactoryState, llm: LLMClient | None = None) -> dict[str, Any]:
    """
    从 knowledge_items 抽样若干条作为证据，生成约 5 条 QA，写入 pending_qa 与 qa_samples。
    """
    items = list(state.get("knowledge_items", []))
    if not items:
        logger.warning("[generate_qa] 当前无知识条目，跳过。")
        return {}

    plans = state.get("topic_plans") or []
    idx = int(state.get("current_topic_index", 0)) % max(len(plans), 1)
    cur_topic = plans[idx]["topic"] if plans else ""

    # 优先采样与当前轮转主题一致的知识，否则全库随机
    pool = [it for it in items if it.get("topic") == cur_topic] or items
    sample_n = min(max(6, len(pool)), 12)
    evidence = random.sample(pool, k=min(sample_n, len(pool)))

    target_count = config.QA_BATCH_SIZE
    client = llm or LLMClient()
    template = config.load_prompt("generate_qa.txt")
    prompt = (
        template.replace("<<KNOWLEDGE_JSON>>", json.dumps(evidence, ensure_ascii=False)).replace(
            "<<TARGET_COUNT>>", str(target_count)
        )
    )

    new_qas: list[QASample] = []
    try:
        raw = client.complete(prompt, temperature=0.55)
        arr = parse_json_array(raw)
    except (JSONParseError, Exception) as e:  # noqa: BLE001
        logger.exception("[generate_qa] 解析失败，本批次跳过：%s", e)
        return {}

    valid_kids = {it["kid"] for it in evidence}
    for obj in arr:
        if not isinstance(obj, dict):
            continue
        try:
            qtype = str(obj["question_type"])
            diff = str(obj["difficulty"])
            query = str(obj["query"]).strip()
            answer = str(obj["answer"]).strip()
            eids = [str(x) for x in obj.get("evidence_kids", [])]
            if not query or not answer or not eids:
                continue
            if any(k not in valid_kids for k in eids):
                logger.warning("[generate_qa] evidence_kids 不在抽样证据内，丢弃：%s", eids)
                continue
            qid = f"q-{uuid.uuid4().hex[:12]}"
            qa: QASample = {
                "qid": qid,
                "topic": str(obj.get("topic") or (evidence[0]["topic"] if evidence else "")),
                "subtopic": str(obj.get("subtopic") or ""),
                "question_type": qtype,  # type: ignore[assignment]
                "difficulty": diff,  # type: ignore[assignment]
                "query": query,
                "answer": answer,
                "evidence_kids": eids,
                "review_status": "pending",
                "review_reason": "",
                "revised_times": int(obj.get("revised_times", 0) or 0),
            }
            new_qas.append(qa)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("[generate_qa] 丢弃无效 QA：%s | data=%s", e, obj)

    pending = list(state.get("pending_qa", [])) + new_qas
    history = list(state.get("qa_samples", [])) + new_qas
    logger.info("[generate_qa] 本批新增 QA=%s | 待审核队列=%s", len(new_qas), len(pending))
    return {"pending_qa": pending, "qa_samples": history}
