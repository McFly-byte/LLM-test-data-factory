"""review_qa 节点：审核 pending 中仍处于 pending 状态的 QA。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app import config
from app.state import FactoryState, KnowledgeItem, QASample
from app.utils.json_parser import JSONParseError, parse_json_object
from app.utils.llm import LLMClient
from app.utils.similarity import is_near_duplicate

logger = logging.getLogger(__name__)


def review_qa(state: FactoryState, llm: LLMClient | None = None) -> dict[str, Any]:
    """
    对 pending_qa 中 review_status == pending 的样本逐条调用审核模型。
    失败时保留原状态并记录原因，避免中断整图。
    """
    pending = list(state.get("pending_qa", []))
    if not pending:
        logger.info("[review_qa] 待审核队列为空，跳过。")
        return {}

    knowledge = {k["kid"]: k for k in state.get("knowledge_items", [])}
    accepted = list(state.get("accepted_qa", []))
    accepted_queries = [qa["query"] for qa in accepted]

    template = config.load_prompt("review_qa.txt")
    client = llm or LLMClient()
    updated: list[QASample] = []

    for qa in pending:
        st = qa.get("review_status", "pending")
        if st != "pending":
            updated.append(qa)
            continue

        evidence = [knowledge[k] for k in qa.get("evidence_kids", []) if k in knowledge]
        if not evidence:
            qa = dict(qa)
            qa["review_status"] = "rejected"
            qa["review_reason"] = "证据缺失：evidence_kids 无法映射到知识条目"
            qa["risk_tags"] = ["证据缺失"]
            updated.append(qa)
            continue

        # 代码层近重复预检（与已接受集合比较）
        thr = float(state.get("duplicate_threshold", config.DUPLICATE_THRESHOLD))
        if is_near_duplicate(qa.get("query", ""), accepted_queries, thr):
            qa = dict(qa)
            qa["review_status"] = "rejected"
            qa["review_reason"] = f"与已接受 query 近重复（相似度阈值={thr}）"
            qa["risk_tags"] = ["疑似重复"]
            updated.append(qa)
            continue

        prompt = (
            template.replace("<<QA_JSON>>", json.dumps(qa, ensure_ascii=False))
            .replace("<<EVIDENCE_JSON>>", json.dumps(evidence, ensure_ascii=False))
            .replace("<<ACCEPTED_QUERIES_JSON>>", json.dumps(accepted_queries, ensure_ascii=False))
        )

        try:
            raw = client.complete(prompt, temperature=0.2)
            obj = parse_json_object(raw)
            status = str(obj.get("review_status", "")).strip()
            reason = str(obj.get("review_reason", "")).strip()
            tags = [str(x) for x in obj.get("risk_tags", []) if str(x).strip()]
            if status not in ("accepted", "rejected"):
                raise JSONParseError(f"非法 review_status: {status}")
            qa = dict(qa)
            qa["review_status"] = status  # type: ignore[assignment]
            qa["review_reason"] = reason or ("通过" if status == "accepted" else "未通过")
            if tags:
                qa["risk_tags"] = tags
            # 模型认为可接受但仍近重复：双保险
            if status == "accepted" and is_near_duplicate(qa.get("query", ""), accepted_queries, thr):
                qa["review_status"] = "rejected"
                qa["review_reason"] = "模型接受但代码复查发现近重复"
                qa["risk_tags"] = list(set(tags + ["疑似重复"]))
        except (JSONParseError, Exception) as e:  # noqa: BLE001
            logger.exception("[review_qa] 单条审核失败，标记为 rejected 以便修订：%s", e)
            qa = dict(qa)
            qa["review_status"] = "rejected"
            qa["review_reason"] = f"审核解析失败：{e}"
            qa["risk_tags"] = ["解析失败"]

        updated.append(qa)

    logger.info("[review_qa] 完成一轮审核，pending 条数=%s", len(updated))
    return {"pending_qa": updated}
