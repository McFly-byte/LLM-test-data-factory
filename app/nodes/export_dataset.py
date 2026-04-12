"""export_dataset 节点：导出 knowledge.jsonl、dataset_full.jsonl、dataset_eval.csv。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.state import FactoryState, KnowledgeItem, QASample
from app.utils.csv_export import write_query_answer_csv

logger = logging.getLogger(__name__)


def export_dataset(state: FactoryState) -> dict[str, Any]:
    """将知识条目与 QA 样本写入 export_dir。"""
    export_dir = Path(state.get("export_dir", "outputs"))
    export_dir.mkdir(parents=True, exist_ok=True)

    knowledge_path = export_dir / "knowledge.jsonl"
    full_path = export_dir / "dataset_full.jsonl"
    csv_path = export_dir / "dataset_eval.csv"

    knowledge_items: list[KnowledgeItem] = list(state.get("knowledge_items", []))
    accepted: list[QASample] = list(state.get("accepted_qa", []))
    rejected: list[QASample] = list(state.get("rejected_qa", []))
    pending: list[QASample] = list(state.get("pending_qa", []))

    with knowledge_path.open("w", encoding="utf-8") as f:
        for it in knowledge_items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    with full_path.open("w", encoding="utf-8") as f:
        for qa in accepted + rejected + pending:
            f.write(json.dumps(qa, ensure_ascii=False) + "\n")

    rows = [{"query": qa.get("query", ""), "answer": qa.get("answer", "")} for qa in accepted]
    write_query_answer_csv(rows, csv_path)

    logger.info(
        "[export_dataset] 已导出：knowledge=%s full=%s csv=%s",
        knowledge_path.resolve(),
        full_path.resolve(),
        csv_path.resolve(),
    )
    return {"done": True}
