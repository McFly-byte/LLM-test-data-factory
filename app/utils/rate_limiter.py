"""
硅基流动等 OpenAI 兼容接口的客户端侧限流：滑动 60 秒窗口上的 RPM + TPM。

说明：
- RPM：窗口内「已发起请求」次数（每次 API 调用计 1，含失败重试的每一次尝试）。
- TPM：窗口内「已记录 token」之和；成功响应优先使用返回的 usage；失败时按输入侧粗估计入，偏保守。
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

_WINDOW_SEC = 60.0


def rough_token_estimate(text: str) -> int:
    """粗估 token 数（略偏保守，降低顶穿 TPM 的概率；无 tiktoken 依赖）。"""
    if not text:
        return 1
    # 中英混排：偏高估一点（字符 * 0.65）并加固定开销
    return max(32, int(len(text) * 0.65) + 80)


class SlidingWindowRateLimiter:
    """单进程内共享的 RPM + TPM 滑动窗口限流器。"""

    def __init__(self, *, rpm_limit: int, tpm_limit: int) -> None:
        self._rpm_limit = max(1, int(rpm_limit))
        self._tpm_limit = max(1, int(tpm_limit))
        self._req_at: deque[float] = deque()
        self._tok: deque[tuple[float, int]] = deque()
        self._lock = Lock()

    def _now(self) -> float:
        return time.monotonic()

    def _evict(self) -> float:
        """清理窗口外事件，返回当前时间。"""
        now = self._now()
        t0 = now - _WINDOW_SEC
        while self._req_at and self._req_at[0] < t0:
            self._req_at.popleft()
        while self._tok and self._tok[0][0] < t0:
            self._tok.popleft()
        return now

    def _tpm_sum(self) -> int:
        return sum(n for _, n in self._tok)

    def acquire_before_request(self, planned_prompt_tokens: int, planned_completion_tokens: int) -> None:
        """
        在发起 HTTP 请求前调用：阻塞直到当前窗口内再增加一次请求不会超过 RPM/TPM 预算。
        成功后会在窗口内登记 1 次 RPM（表示即将发起的一次请求）。
        """
        planned_total = max(1, int(planned_prompt_tokens) + int(planned_completion_tokens))
        sleep_cap = 2.0
        while True:
            with self._lock:
                now = self._evict()
                rpm = len(self._req_at)
                tpm = self._tpm_sum()
                rpm_ok = rpm < self._rpm_limit
                tpm_ok = tpm + planned_total <= self._tpm_limit
                if rpm_ok and tpm_ok:
                    self._req_at.append(now)
                    logger.debug(
                        "[rate_limit] 放行请求 | rpm=%s/%s tpm=%s/%s(+计划=%s)",
                        rpm + 1,
                        self._rpm_limit,
                        tpm,
                        self._tpm_limit,
                        planned_total,
                    )
                    return

                wake = 0.05
                if not rpm_ok and self._req_at:
                    wake = max(wake, self._req_at[0] + _WINDOW_SEC - now)
                if not tpm_ok and self._tok:
                    wake = max(wake, self._tok[0][0] + _WINDOW_SEC - now)
                elif not tpm_ok:
                    wake = max(wake, 0.1)

                sleep_s = min(max(float(wake), 0.02), sleep_cap)
                logger.info(
                    "[rate_limit] 触发等待 %.2fs | rpm=%s/%s tpm=%s/%s 计划增量=%s",
                    sleep_s,
                    rpm,
                    self._rpm_limit,
                    tpm,
                    self._tpm_limit,
                    planned_total,
                )
            time.sleep(sleep_s)

    def record_token_usage(self, total_tokens: int) -> None:
        """请求结束后写入 TPM 计数（prompt+completion 总和）。"""
        tt = max(0, int(total_tokens))
        if tt <= 0:
            return
        with self._lock:
            self._evict()
            self._tok.append((self._now(), tt))

    def record_failed_request_tokens(self, estimated_prompt_tokens: int) -> None:
        """请求失败时保守计入输入侧 token，避免短时间突发再次顶穿 TPM。"""
        self.record_token_usage(max(1, int(estimated_prompt_tokens)))


_limiter_singleton: Optional[SlidingWindowRateLimiter] = None
_limiter_lock = Lock()


def get_rate_limiter() -> Optional[SlidingWindowRateLimiter]:
    """若未启用限流则返回 None。"""
    global _limiter_singleton  # noqa: PLW0603 — 进程内单例
    from app import config  # 延迟导入，避免循环

    if not config.SILICONFLOW_RATE_LIMIT_ENABLED:
        return None
    with _limiter_lock:
        if _limiter_singleton is None:
            _limiter_singleton = SlidingWindowRateLimiter(
                rpm_limit=config.SILICONFLOW_RPM_LIMIT,
                tpm_limit=config.SILICONFLOW_TPM_LIMIT,
            )
        return _limiter_singleton
