"""
LangGraph 编排：StateGraph + 条件路由 + 终止导出。

流程（文字版）：
plan_topics -> generate_knowledge -> generate_qa -> review_qa -> revise_or_accept
->（若满足终止条件则 export_dataset；否则若仍有待复审样本则回到 review_qa；否则继续 generate_knowledge）
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app import config
from app.nodes.export_dataset import export_dataset
from app.nodes.generate_knowledge import generate_knowledge
from app.nodes.generate_qa import generate_qa
from app.nodes.plan_topics import plan_topics
from app.nodes.review_qa import review_qa
from app.nodes.revise_or_accept import revise_or_accept
from app.state import FactoryState
from app.utils.llm import LLMClient
from app.utils.progress import format_factory_snapshot

logger = logging.getLogger(__name__)


def _wrap_node(label: str, run: Any) -> Any:
    """为节点统一打印「进入 / 离开」与状态快照，便于跟踪整条流水线进展。"""

    def _inner(state: FactoryState) -> Any:
        logger.info("[%s] >>> 进入 | %s", label, format_factory_snapshot(state))
        try:
            out = run(state)
        except Exception:
            logger.exception("[%s] <<< 节点执行异常（将向上抛出）", label)
            raise
        if isinstance(out, dict) and out:
            merged: dict[str, Any] = {**dict(state), **out}
            logger.info(
                "[%s] <<< 离开 | 更新键=%s | %s",
                label,
                sorted(out.keys()),
                format_factory_snapshot(merged),
            )
        else:
            logger.info("[%s] <<< 离开 | 无合并更新 | %s", label, format_factory_snapshot(state))
        return out

    return _inner


def _knowledge_char_total(state: FactoryState) -> int:
    return sum(len(it.get("content", "")) for it in state.get("knowledge_items", []))


def _export_ready(state: FactoryState) -> bool:
    """终止条件：通过 QA 数量达标，或知识正文总字数达标。"""
    if state.get("done"):
        return True
    if len(state.get("accepted_qa", [])) >= int(state.get("target_qa_count", config.TARGET_QA_COUNT)):
        return True
    if _knowledge_char_total(state) >= int(state.get("target_knowledge_chars", config.TARGET_KNOWLEDGE_CHARS)):
        return True
    return False


def _needs_review(state: FactoryState) -> bool:
    """是否存在仍待模型审核的样本（review_status == pending）。"""
    return any(q.get("review_status") == "pending" for q in state.get("pending_qa", []))


def route_after_revise(state: FactoryState) -> Literal["export", "review", "grow"]:
    """
    条件路由（保持简单）：
    1) 满足导出/终止条件 -> export
    2) 仍有待审核样本 -> review（通常来自修订后的复审）
    3) 否则继续扩增语料与 QA -> grow
    """
    snap = format_factory_snapshot(state)
    if _export_ready(state):
        logger.info("[route] 满足终止条件 -> export_dataset | %s", snap)
        return "export"
    if _needs_review(state):
        logger.info("[route] 仍有待审核 -> review_qa | %s", snap)
        return "review"
    logger.info("[route] 继续扩增 -> generate_knowledge | %s", snap)
    return "grow"


def build_factory_graph(*, llm: LLMClient | None = None) -> Any:
    """构建并编译 LangGraph。"""
    # 延迟创建客户端：允许在无 API Key 时先完成 import/compile（真正调用节点时再报错）
    holder: dict[str, LLMClient | None] = {"client": llm}

    def _client() -> LLMClient:
        if holder["client"] is None:
            holder["client"] = LLMClient()
        return holder["client"]

    g: StateGraph[FactoryState] = StateGraph(FactoryState)

    g.add_node("plan_topics", _wrap_node("plan_topics", lambda s: plan_topics(s, _client())))
    g.add_node("generate_knowledge", _wrap_node("generate_knowledge", lambda s: generate_knowledge(s, _client())))
    g.add_node("generate_qa", _wrap_node("generate_qa", lambda s: generate_qa(s, _client())))
    g.add_node("review_qa", _wrap_node("review_qa", lambda s: review_qa(s, _client())))
    g.add_node("revise_or_accept", _wrap_node("revise_or_accept", lambda s: revise_or_accept(s, _client())))
    g.add_node("export_dataset", _wrap_node("export_dataset", export_dataset))

    g.set_entry_point("plan_topics")
    g.add_edge("plan_topics", "generate_knowledge")
    g.add_edge("generate_knowledge", "generate_qa")
    g.add_edge("generate_qa", "review_qa")
    g.add_edge("review_qa", "revise_or_accept")

    g.add_conditional_edges(
        "revise_or_accept",
        route_after_revise,
        {
            "export": "export_dataset",
            "review": "review_qa",
            "grow": "generate_knowledge",
        },
    )

    g.add_edge("export_dataset", END)
    compiled = g.compile()
    logger.info("[graph] StateGraph 编译完成：入口 plan_topics -> … -> export_dataset -> END")
    return compiled
