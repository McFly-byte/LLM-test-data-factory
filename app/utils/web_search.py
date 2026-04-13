"""
外部网页检索：为知识生成提供可引用的实时摘要（标题 / URL / 片段）。

支持两种后端（由配置 WEB_SEARCH_BACKEND 决定）：
- duckduckgo：基于 duckduckgo-search，无需 API Key（适合本地演示；部分地区网络可能不可用）
- tavily：需要 TAVILY_API_KEY，检索质量通常更稳定
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, TypedDict

import httpx

from app import config
from app.state import TopicPlan

logger = logging.getLogger(__name__)


class WebSearchHit(TypedDict):
    """单条检索摘要（供注入 prompt / 写入知识溯源）。"""

    title: str
    url: str
    body: str
    source: str  # duckduckgo | tavily


def build_topic_search_query(plan: TopicPlan) -> str:
    """根据当前主题桶构造检索 query（偏技术向，附带年份以提升时效性）。"""
    subs = plan.get("subtopics") or []
    sub = random.choice(subs) if subs else ""
    topic = str(plan.get("topic", "")).strip()
    q = f"{topic} {sub}".strip()
    # 轻量提示模型关注近期资料；不写入过长的 query
    return (q + " LLM RAG 工程实践 2026").strip()[:240]


def _trim(s: str, n: int) -> str:
    s = (s or "").replace("\r", " ").replace("\n", " ").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _search_duckduckgo(query: str) -> list[WebSearchHit]:
    try:
        from duckduckgo_search import DDGS  # type: ignore[import-untyped]
    except ImportError as e:
        logger.warning("[web_search] 未安装 duckduckgo-search，跳过 DuckDuckGo 检索：%s", e)
        return []

    hits: list[WebSearchHit] = []
    n = max(1, int(config.WEB_SEARCH_MAX_RESULTS))
    cap = max(120, int(config.WEB_SEARCH_SNIPPET_CHARS))
    try:
        with DDGS(timeout=max(15, int(config.WEB_SEARCH_HTTP_TIMEOUT_SEC))) as ddgs:
            # 不传 backend：由库选择可用线路；部分环境 backend="api" 更稳，可自行改源码尝试
            rows = ddgs.text(query, max_results=n)
        for r in rows or []:
            url = str(r.get("href") or r.get("url") or "").strip()
            title = str(r.get("title") or "").strip() or url
            body = _trim(str(r.get("body") or ""), cap)
            if not url:
                continue
            hits.append(WebSearchHit(title=title, url=url, body=body, source="duckduckgo"))
    except Exception as e:  # noqa: BLE001
        logger.warning("[web_search] DuckDuckGo 检索失败（将回退为无检索上下文）：%s", e)
        return []
    return hits


def _search_tavily(query: str) -> list[WebSearchHit]:
    key = (config.TAVILY_API_KEY or "").strip()
    if not key:
        logger.warning("[web_search] 未设置 TAVILY_API_KEY，无法使用 Tavily。")
        return []

    n = max(1, int(config.WEB_SEARCH_MAX_RESULTS))
    cap = max(120, int(config.WEB_SEARCH_SNIPPET_CHARS))
    payload: dict[str, Any] = {
        "api_key": key,
        "query": query,
        "search_depth": "basic",
        "max_results": n,
        "include_answer": False,
    }
    try:
        with httpx.Client(timeout=float(config.WEB_SEARCH_HTTP_TIMEOUT_SEC)) as client:
            r = client.post("https://api.tavily.com/search", json=payload)
            r.raise_for_status()
            data = r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("[web_search] Tavily 检索失败（将回退为无检索上下文）：%s", e)
        return []

    hits: list[WebSearchHit] = []
    for it in data.get("results") or []:
        if not isinstance(it, dict):
            continue
        url = str(it.get("url") or "").strip()
        title = str(it.get("title") or "").strip() or url
        body = _trim(str(it.get("content") or it.get("snippet") or ""), cap)
        if not url:
            continue
        hits.append(WebSearchHit(title=title, url=url, body=body, source="tavily"))
    return hits


def search_for_topic_plan(plan: TopicPlan) -> list[WebSearchHit]:
    """
    针对当前 TopicPlan 拉取外部检索摘要。
    若未启用检索或全部后端失败，返回空列表（上层仍可纯模型生成）。
    """
    if not config.WEB_SEARCH_ENABLED:
        return []

    q = build_topic_search_query(plan)
    backend = (config.WEB_SEARCH_BACKEND or "duckduckgo").lower().strip()
    logger.info("[web_search] query=%s backend=%s", q, backend)

    if backend == "tavily":
        hits = _search_tavily(q)
        if hits:
            return hits
        if config.WEB_SEARCH_FALLBACK_DUCKDUCKGO:
            logger.info("[web_search] Tavily 无结果或失败，尝试 DuckDuckGo 回退。")
            return _search_duckduckgo(q)
        return []

    # 默认 duckduckgo
    return _search_duckduckgo(q)


def hits_as_prompt_json(hits: list[WebSearchHit]) -> str:
    """供 prompt 注入的 JSON 数组字符串。"""
    return json.dumps(hits, ensure_ascii=False)
