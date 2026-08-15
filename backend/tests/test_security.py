"""
「隐盾」安全模块测试 — 限流 / 鉴权 / CORS 白名单
================================================
- ⚠️ 不 import app.main（避免触发 PaddleOCR/YOLO 预热）；测试内构造最小 app
- 覆盖：
  1. RateLimiter 纯逻辑（限内放行 / 超限拒绝 / 窗口重置 / key 隔离）
  2. RateLimitMiddleware 集成（429 + Retry-After / /api/health 不限流 / OPTIONS 不计配额）
  3. require_api_key 鉴权（默认关闭放行 / 开启后 401-200）
  4. CORS 白名单预检（开发源放行 / 未知源拒绝）
"""

import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import SecurityConfig
from app.core.security import RateLimiter, RateLimitMiddleware, require_api_key


# ==================== 1. RateLimiter 纯逻辑 ====================

class TestRateLimiter:
    def test_allow_within_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        assert limiter.allow("ip-1") is True
        assert limiter.allow("ip-1") is True
        assert limiter.allow("ip-1") is True

    def test_block_over_limit(self):
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert limiter.allow("ip-1") is True
        assert limiter.allow("ip-1") is False

    def test_reset_after_window(self):
        limiter = RateLimiter(max_requests=2, window_seconds=1)
        assert limiter.allow("ip-1") is True
        assert limiter.allow("ip-1") is True
        assert limiter.allow("ip-1") is False
        time.sleep(1.1)  # 窗口滑出
        assert limiter.allow("ip-1") is True

    def test_keys_isolated(self):
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        assert limiter.allow("ip-1") is True
        assert limiter.allow("ip-1") is False
        assert limiter.allow("ip-2") is True


# ==================== 辅助：测试内构造最小 app ====================

def _build_app(with_rate_limit: bool = True, with_cors: bool = False) -> FastAPI:
    """构造最小 FastAPI app（不 import app.main），挂与 main.py 相同的中间件"""
    app = FastAPI()
    if with_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=SecurityConfig.CORS_ALLOW_ORIGINS,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if with_rate_limit:
        app.add_middleware(RateLimitMiddleware)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    @app.get("/api/health")
    def health():
        return {"status": "healthy"}

    return app


def _build_auth_app() -> FastAPI:
    """构造带 require_api_key 依赖的最小 app（模拟 main.py 的 router 级依赖）"""
    app = FastAPI()

    @app.get("/api/ping", dependencies=[Depends(require_api_key)])
    def ping():
        return {"ok": True}

    return app


# ==================== 2. RateLimitMiddleware 集成 ====================

class TestRateLimitMiddleware:
    def test_429_over_limit(self, monkeypatch):
        monkeypatch.setattr(SecurityConfig, "RATE_LIMIT_PER_MINUTE", 3)
        client = TestClient(_build_app())
        for _ in range(3):
            assert client.get("/api/ping").status_code == 200
        resp = client.get("/api/ping")
        assert resp.status_code == 429
        assert resp.headers.get("retry-after") is not None
        body = resp.json()
        assert body["type"] == "RateLimitExceeded"
        assert "success" in body and body["success"] is False

    def test_health_not_limited(self, monkeypatch):
        monkeypatch.setattr(SecurityConfig, "RATE_LIMIT_PER_MINUTE", 1)
        client = TestClient(_build_app())
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/health").status_code == 200  # 第二次仍 200

    def test_options_preflight_not_counted(self, monkeypatch):
        """OPTIONS 预检不计入配额，避免 CORS 预检消耗额度"""
        monkeypatch.setattr(SecurityConfig, "RATE_LIMIT_PER_MINUTE", 2)
        client = TestClient(_build_app())
        # 3 次 OPTIONS 预检（超过配额）也不应被限流
        for _ in range(3):
            resp = client.options("/api/ping", headers={"Origin": "http://localhost:5173"})
            assert resp.status_code != 429
        # 真正的业务请求仍正常计数
        assert client.get("/api/ping").status_code == 200
        assert client.get("/api/ping").status_code == 200
        assert client.get("/api/ping").status_code == 429


# ==================== 3. require_api_key 鉴权 ====================

class TestAuth:
    def test_disabled_when_no_key(self, monkeypatch):
        monkeypatch.setattr(SecurityConfig, "API_KEY", "")
        client = TestClient(_build_auth_app())
        assert client.get("/api/ping").status_code == 200

    def test_requires_key_when_enabled(self, monkeypatch):
        monkeypatch.setattr(SecurityConfig, "API_KEY", "secret-key-123")
        client = TestClient(_build_auth_app())
        # 无头 → 401
        assert client.get("/api/ping").status_code == 401
        # 错误头 → 401
        assert client.get("/api/ping", headers={"X-API-Key": "wrong"}).status_code == 401
        # 正确头 → 200
        assert client.get("/api/ping", headers={"X-API-Key": "secret-key-123"}).status_code == 200


# ==================== 4. CORS 白名单预检 ====================

class TestCors:
    def test_dev_origin_allowed(self):
        client = TestClient(_build_app(with_rate_limit=False, with_cors=True))
        resp = client.options(
            "/api/ping",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"

    def test_unknown_origin_rejected(self):
        client = TestClient(_build_app(with_rate_limit=False, with_cors=True))
        resp = client.options(
            "/api/ping",
            headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in resp.headers
