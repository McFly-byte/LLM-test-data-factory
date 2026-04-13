"""轻量 LLM 调用封装：支持重试、环境变量配置与硅基流动 RPM/TPM 限流。"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from openai import OpenAI

from app import config
from app.utils.rate_limiter import get_rate_limiter, rough_token_estimate

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "你是严谨的中文技术写作助手，必须严格遵守用户格式要求。"


def _estimate_prompt_tokens(prompt: str) -> int:
    """粗估本次请求的 prompt token（system + user）。"""
    return rough_token_estimate(_SYSTEM_PROMPT) + rough_token_estimate(prompt)


def _usage_total_tokens(resp: Any) -> Optional[int]:
    """从 SDK 响应提取 total_tokens；若无则尝试 prompt+completion。"""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return None
    total = getattr(usage, "total_tokens", None)
    if total is not None:
        return int(total)
    pt = getattr(usage, "prompt_tokens", None)
    ct = getattr(usage, "completion_tokens", None)
    if pt is not None and ct is not None:
        return int(pt) + int(ct)
    return None


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
        每次尝试前按配置的 RPM/TPM 做滑动窗口限流（见 rate_limiter）。
        """
        last_err: Exception | None = None
        limiter = get_rate_limiter()
        est_in = _estimate_prompt_tokens(prompt)
        reserve = int(config.SILICONFLOW_TPM_OUTPUT_RESERVE)

        for attempt in range(1, self._max_retries + 1):
            if limiter is not None:
                limiter.acquire_before_request(est_in, reserve)
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    temperature=temperature,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                msg = resp.choices[0].message.content or ""
                text = msg.strip()
                if limiter is not None:
                    used = _usage_total_tokens(resp)
                    if used is None:
                        used = est_in + rough_token_estimate(text)
                    limiter.record_token_usage(used)
                else:
                    used = _usage_total_tokens(resp)
                logger.info(
                    "[llm] 调用成功 | model=%s | 尝试=%s/%s | prompt≈%s字 | 回复≈%s字 | tokens=%s",
                    self._model,
                    attempt,
                    self._max_retries,
                    len(prompt),
                    len(text),
                    used if used is not None else est_in + rough_token_estimate(text),
                )
                return text
            except Exception as e:  # noqa: BLE001 — 展示层捕获，记录后继续重试
                if limiter is not None:
                    # 请求已计入 RPM；失败时保守按输入侧计入 TPM，降低连续突发风险
                    limiter.record_failed_request_tokens(est_in)
                last_err = e
                logger.warning("LLM 调用失败（第 %s/%s 次）: %s", attempt, self._max_retries, e)
                time.sleep(min(2.0 * attempt, 8.0))
        assert last_err is not None
        raise last_err
