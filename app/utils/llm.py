"""轻量 LLM 调用封装：支持重试与环境变量配置。"""

from __future__ import annotations

import logging
import time
from typing import Optional

from openai import OpenAI

from app import config

logger = logging.getLogger(__name__)


class LLMClient:
    """基于 OpenAI 兼容接口的文本补全客户端。"""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = config.LLM_MAX_RETRIES,
        timeout: float = config.LLM_TIMEOUT_SEC,
    ) -> None:
        key = api_key or config.OPENAI_API_KEY
        if not key:
            raise ValueError(
                "未设置 API Key：请在环境变量 SILICONFLOW_API_KEY 中填入硅基流动密钥，"
                "或设置 OPENAI_API_KEY（兼容其它 OpenAI 兼容服务商）。"
            )
        self._client = OpenAI(api_key=key, base_url=base_url or config.OPENAI_BASE_URL, timeout=timeout)
        self._model = model or config.OPENAI_MODEL
        self._max_retries = max(1, max_retries)

    def complete(self, prompt: str, *, temperature: float = 0.4) -> str:
        """
        调用聊天补全，返回 assistant 文本。
        失败时按次数重试，每次间隔轻微退避。
        """
        last_err: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": "你是严谨的中文技术写作助手，必须严格遵守用户格式要求。"},
                        {"role": "user", "content": prompt},
                    ],
                )
                msg = resp.choices[0].message.content or ""
                return msg.strip()
            except Exception as e:  # noqa: BLE001 — 展示层捕获，记录后继续重试
                last_err = e
                logger.warning("LLM 调用失败（第 %s/%s 次）: %s", attempt, self._max_retries, e)
                time.sleep(min(2.0 * attempt, 8.0))
        assert last_err is not None
        raise last_err
