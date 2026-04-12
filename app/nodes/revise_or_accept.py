"""revise_or_accept 节点：接受合格样本；不合格样本最多修订 max_revision_rounds 次。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app import config
from app.state import FactoryState, KnowledgeItem, QASample
from app.utils.json_parser import JSONParseError, parse_json_object
from app.utils.llm import LLMClient

logger = logging.getLogger(__name__)


def revise_or_accept(state: FactoryState, llm: LLMClient | None = None) -> dict[str, Any]:
    """
    - accepted：移入 accepted_qa
    - rejected 且 revised_times < max：调用修订提示词，修订后置为 pending 以便复审
    - rejected 且 revised_times >= max：移入 rejected_qa
    """
    pending = list(state.get("pending_qa", []))
    if not pending:
        logger.info("[revise_or_accept] 无待处理 QA。")
        return {}

    knowledge = {k["kid"]: k for k in state.get("knowledge_items", [])}
    max_r = int(state.get("max_revision_rounds", config.MAX_REVISION_ROUNDS))

    accepted_all = list(state.get("accepted_qa", []))
    rejected_all = list(state.get("rejected_qa", []))

    client = llm or LLMClient()
    template = config.load_prompt("revise_qa.txt")

    new_pending: list[QASample] = []

    for qa in pending:
        status = qa.get("review_status", "pending")
        if status == "accepted":
            accepted_all.append(qa)
            logger.info("[revise_or_accept] 接受：%s | query=%s", qa.get("qid"), qa.get("query", "")[:40])
            continue

        if status != "rejected":
            # 仍在 pending 审核流程的样本，原样保留
            new_pending.append(qa)
            continue

        revised_times = int(qa.get("revised_times", 0) or 0)
        if revised_times >= max_r:
            rejected_all.append(qa)
            logger.info("[revise_or_accept] 拒绝入库（超过修订次数）：%s", qa.get("qid"))
            continue

        evidence = [knowledge[k] for k in qa.get("evidence_kids", []) if k in knowledge]
        if not evidence:
            rejected_all.append(qa)
            continue

        prompt = (
            template.replace("<<QA_JSON>>", json.dumps(qa, ensure_ascii=False))
            .replace("<<REVIEW_REASON>>", str(qa.get("review_reason", "")))
            .replace("<<EVIDENCE_JSON>>", json.dumps(evidence, ensure_ascii=False))
        )

        try:
            raw = client.complete(prompt, temperature=0.35)
            obj = parse_json_object(raw)
            nq = str(obj.get("query", "")).strip()
            na = str(obj.get("answer", "")).strip()
            kids = [str(x) for x in obj.get("evidence_kids", [])]
            allowed = {k["kid"] for k in evidence}
            if not nq or not na or not kids or any(k not in allowed for k in kids):
                raise JSONParseError("修订输出字段不合法或 evidence_kids 越界")

            fixed: QASample = dict(qa)
            fixed["query"] = nq
            fixed["answer"] = na
            fixed["evidence_kids"] = kids
            fixed["review_status"] = "pending"
            fixed["revised_times"] = revised_times + 1
            fixed["review_reason"] = ""
            new_pending.append(fixed)
            logger.info(
                "[revise_or_accept] 已修订（%s/%s）：%s",
                fixed["revised_times"],
                max_r,
                fixed.get("qid"),
            )
        except (JSONParseError, Exception) as e:  # noqa: BLE001
            logger.exception("[revise_or_accept] 修订失败，保留 rejected 并计数+1：%s", e)
            bumped: QASample = dict(qa)
            bumped["revised_times"] = revised_times + 1
            if bumped["revised_times"] >= max_r:
                rejected_all.append(bumped)
            else:
                bumped["review_status"] = "pending"
                bumped["review_reason"] = f"修订解析失败：{e}"
                new_pending.append(bumped)

    logger.info(
        "[revise_or_accept] 汇总：accepted=%s rejected=%s pending=%s",
        len(accepted_all),
        len(rejected_all),
        len(new_pending),
    )
    return {"pending_qa": new_pending, "accepted_qa": accepted_all, "rejected_qa": rejected_all}
