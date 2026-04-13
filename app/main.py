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

# 须先于 `import app.config`：否则 .env 中的 FACTORY_DOMAIN 等不会在配置模块求值时载入
load_dotenv(_ROOT / ".env", override=False)

from app import config
from app.graph import build_factory_graph
from app.state import new_factory_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("main")


def main() -> None:
    export_dir = str(config.PROJECT_ROOT / "outputs")
    logger.info("======== LLM Test Data Factory 启动 ========")
    logger.info(
        "配置摘要 | model=%s | base_url=%s | 目标QA=%s | 目标知识字数≈%s | 导出目录=%s",
        config.OPENAI_MODEL,
        config.OPENAI_BASE_URL,
        config.TARGET_QA_COUNT,
        config.TARGET_KNOWLEDGE_CHARS,
        export_dir,
    )
    logger.info(
        "功能开关 | 限流=%s rpm=%s tpm=%s | 网页检索=%s backend=%s",
        config.SILICONFLOW_RATE_LIMIT_ENABLED,
        config.SILICONFLOW_RPM_LIMIT,
        config.SILICONFLOW_TPM_LIMIT,
        config.WEB_SEARCH_ENABLED,
        config.WEB_SEARCH_BACKEND,
    )
    dom = (config.DEFAULT_DOMAIN or "")[:120]
    logger.info("领域 domain（前120字）| %s%s", dom, "…" if len(config.DEFAULT_DOMAIN or "") > 120 else "")

    init = new_factory_state(
        domain=config.DEFAULT_DOMAIN,
        target_knowledge_chars=config.TARGET_KNOWLEDGE_CHARS,
        target_qa_count=config.TARGET_QA_COUNT,
        duplicate_threshold=config.DUPLICATE_THRESHOLD,
        max_revision_rounds=config.MAX_REVISION_ROUNDS,
        export_dir=export_dir,
    )

    graph = build_factory_graph()
    logger.info("LangGraph 已编译，开始 invoke（recursion_limit=500）…")

    # 防止极端情况下递归过深；可按机器与任务调大
    final_state = graph.invoke(init, {"recursion_limit": 500})
    logger.info("LangGraph invoke 已结束。")

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
