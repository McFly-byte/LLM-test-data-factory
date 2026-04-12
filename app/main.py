"""
最小可运行入口：初始化默认状态，编译并运行 LangGraph，打印统计信息。

运行方式（在项目根目录）：
  python app/main.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# 兼容 `python app/main.py`：将项目根目录加入 sys.path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

from app import config
from app.graph import build_factory_graph
from app.state import new_factory_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("main")


def main() -> None:
    load_dotenv(override=False)

    export_dir = str(config.PROJECT_ROOT / "outputs")
    init = new_factory_state(
        domain=config.DEFAULT_DOMAIN,
        target_knowledge_chars=config.TARGET_KNOWLEDGE_CHARS,
        target_qa_count=config.TARGET_QA_COUNT,
        duplicate_threshold=config.DUPLICATE_THRESHOLD,
        max_revision_rounds=config.MAX_REVISION_ROUNDS,
        export_dir=export_dir,
    )

    graph = build_factory_graph()

    # 防止极端情况下递归过深；可按机器与任务调大
    final_state = graph.invoke(init, {"recursion_limit": 500})

    kc = sum(len(it.get("content", "")) for it in final_state.get("knowledge_items", []))
    logger.info("======== 运行结束统计 ========")
    logger.info("知识条目数：%s", len(final_state.get("knowledge_items", [])))
    logger.info("知识正文总字数（近似）：%s / 目标 %s", kc, final_state.get("target_knowledge_chars"))
    logger.info("已接受 QA：%s / 目标 %s", len(final_state.get("accepted_qa", [])), final_state.get("target_qa_count"))
    logger.info("已拒绝 QA：%s", len(final_state.get("rejected_qa", [])))
    logger.info("待处理 pending QA：%s", len(final_state.get("pending_qa", [])))
    logger.info("导出目录：%s", Path(final_state.get("export_dir", export_dir)).resolve())
    logger.info("完成标记 done=%s", final_state.get("done"))


if __name__ == "__main__":
    main()
