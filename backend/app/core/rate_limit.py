"""Rate limit simples por IP, em memória (janela fixa).

Trade-off: cada worker do uvicorn tem o próprio contador, então o limite efetivo
é aproximado (até N workers x limite). Suficiente contra força bruta de login e
flood de eventos; para limite exato seria preciso um storage compartilhado.
O IP vem de CF-Connecting-IP (Cloudflare Tunnel); o backend só é exposto por ele.
"""
import math
import threading
import time
from typing import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings


class FixedWindowLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic, max_keys: int = 50_000):
        self._clock = clock
        self._max_keys = max_keys
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()
        self.enabled = True

    def hit(self, key: str, limit: int, window: int) -> tuple[bool, int]:
        """Conta uma requisição. Retorna (permitida, segundos até liberar)."""
        now = self._clock()
        with self._lock:
            start, count = self._buckets.get(key, (now, 0))
            if now - start >= window:
                start, count = now, 0
            count += 1
            if key not in self._buckets and len(self._buckets) >= self._max_keys:
                self._evict(now, window)
            self._buckets[key] = (start, count)
        retry_after = max(1, math.ceil(window - (now - start)))
        return count <= limit, retry_after

    def _evict(self, now: float, window: int) -> None:
        expired = [k for k, (start, _) in self._buckets.items() if now - start >= window]
        for k in expired:
            del self._buckets[k]
        if len(self._buckets) >= self._max_keys:
            # Ainda cheio: descarta as janelas mais antigas (metade)
            for k, _ in sorted(self._buckets.items(), key=lambda kv: kv[1][0])[: self._max_keys // 2]:
                del self._buckets[k]

    def size(self) -> int:
        return len(self._buckets)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


limiter = FixedWindowLimiter()
limiter.enabled = settings.RATE_LIMIT_ENABLED


def client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(scope: str, limit: int, window: int = 60):
    """Dependência FastAPI: até `limit` requisições por IP a cada `window` segundos."""

    def dependency(request: Request) -> None:
        if not limiter.enabled:
            return
        allowed, retry_after = limiter.hit(f"{scope}:{client_ip(request)}", limit, window)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas. Aguarde um pouco e tente novamente.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
