"""工厂运行进度：单行快照，便于各节点与路由统一打日志。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.state import FactoryState


def format_factory_snapshot(state: Mapping[str, Any] | FactoryState) -> str:
    """从当前状态抽取关键计数，拼成一行（不含敏感信息）。"""
    items = state.get("knowledge_items") or []
    kc = sum(len(it.get("content", "") or "") for it in items)
    tgt_q = state.get("target_qa_count")
    tgt_k = state.get("target_knowledge_chars")
    acc = len(state.get("accepted_qa") or [])
    return (
        f"plans={len(state.get('topic_plans') or [])} "
        f"topic_idx={state.get('current_topic_index', 0)} "
        f"knowledge={len(items)} kchars≈{kc}/{tgt_k} "
        f"accepted={acc}/{tgt_q} "
        f"pending={len(state.get('pending_qa') or [])} "
        f"rejected={len(state.get('rejected_qa') or [])} "
        f"done={bool(state.get('done', False))}"
    )
