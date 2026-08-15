"""
================================================================
「隐盾」安全模块 — 限流 + 鉴权
================================================================
- RateLimiter          : 按 key（客户端 IP）滑动窗口限流，纯逻辑、可单测
- RateLimitMiddleware  : Starlette 中间件，仅对 /api/*（除 /api/health）限流，超限返回 429
- require_api_key      : 可选 API Key 鉴权依赖（设 YINDUN_API_KEY 环境变量开启，默认关闭）

设计要点：
- 仅标准库 + fastapi/starlette，无重型依赖（不 import app.main / 不触发模型预热）
- 限流按客户端 IP 计数；OPTIONS 预检请求不计入配额（避免 CORS 预检消耗额度）
- 鉴权默认关闭，保持产品「无需注册登录」的零门槛理念；部署时设 API_KEY 即全 API 开启
"""

import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Header, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

from app.core.config import SecurityConfig


class RateLimiter:
    """按 key 的滑动窗口限流器（线程安全，惰性清理过期时间戳）"""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """窗口内未超限则记录本次请求并返回 True，否则返回 False"""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            # 惰性清理过期时间戳（窗口滑出后自动释放内存与配额）
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """仅对 /api/*（除 /api/health）按客户端 IP 限流，超限返回 429 + Retry-After"""

    def __init__(self, app):
        super().__init__(app)
        self._limiter = RateLimiter(
            SecurityConfig.RATE_LIMIT_PER_MINUTE,
            SecurityConfig.RATE_LIMIT_WINDOW_SECONDS,
        )

    async def dispatch(self, request, call_next):
        path = request.url.path
        # OPTIONS 预检（CORS）不计入配额；健康检查/文档不限流（运维便利）
        if (
            request.method != "OPTIONS"
            and path.startswith("/api/")
            and not path.startswith("/api/health")
        ):
            client_ip = request.client.host if request.client else "unknown"
            if not self._limiter.allow(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": "请求过于频繁，请稍后再试",
                        "type": "RateLimitExceeded",
                    },
                    headers={"Retry-After": str(SecurityConfig.RATE_LIMIT_WINDOW_SECONDS)},
                )
        return await call_next(request)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """可选 API Key 鉴权：SecurityConfig.API_KEY 为空则放行，否则校验 X-API-Key 头"""
    expected = SecurityConfig.API_KEY
    if not expected:
        # 开发模式：鉴权关闭，保持零门槛
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="无效或缺失的 API Key")
