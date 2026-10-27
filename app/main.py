"""商品写真の仕分け（見本）。写真を上げると、何が写っているかを判定して仕分け先を返す。
- GET  /               … 画面（写真を選ぶ → 結果と最近の履歴）
- POST /api/classify   … 画像1枚（multipart の file）→ 上位3件・仕分け先・かかった時間
- GET  /api/history    … 最近20件の判定
- GET  /healthz        … 動いているか"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .db import Store
from .model import BadImage, Classifier, judge, load_image

MAX_BYTES = 10 * 1024 * 1024
RATE_PER_MIN = int(os.environ.get("RATE_PER_MIN", "20"))
PAGE = (Path(__file__).resolve().parent / "page.html").read_text(encoding="utf-8")


class RateLimit:
    """送り元ごとに1分あたりの回数を数える（公開の見本なので、連打で CPU を占有されないように）"""

    def __init__(self, per_min: int):
        self.per_min, self.hits, self.lock = per_min, {}, threading.Lock()

    def ok(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self.lock:
            q = self.hits.setdefault(key, deque())
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_min:
                return False
            q.append(now)
            if len(self.hits) > 10_000:                                  # 送り元が増え続けても覚え続けない
                self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] <= 60}
            return True


def client_ip(request: Request) -> str:
    """手前の nginx（同じサーバーの中）から来た時だけ X-Real-IP を信じる。外から直接来た偽のヘッダーは使わない"""
    peer = request.client.host if request.client else "?"
    if peer in ("127.0.0.1", "::1") or peer.startswith("172."):
        return request.headers.get("x-real-ip", peer)
    return peer


def create_app(classifier=None, store: Store | None = None, rate: RateLimit | None = None) -> FastAPI:
    app = FastAPI(title="商品写真の仕分け（見本）", docs_url=None, redoc_url=None, openapi_url=None)
    clf = classifier or Classifier()                                      # モデルが読めなければ起動しない（黙って動かない状態にしない）
    db = store or Store()
    limit = rate or RateLimit(RATE_PER_MIN)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        r = await call_next(request)
        r.headers["X-Content-Type-Options"] = "nosniff"
        r.headers["X-Frame-Options"] = "DENY"
        r.headers["Referrer-Policy"] = "no-referrer"
        r.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
        return r

    @app.get("/", response_class=HTMLResponse)
    def page():
        return PAGE

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/api/history")
    def history():
        return {"items": db.recent(20)}

    @app.post("/api/classify")
    async def classify(request: Request, file: UploadFile = File(...)):
        if not limit.ok(client_ip(request)):
            raise HTTPException(429, "回数の上限です。1分ほど待ってからもう一度お試しください")
        data = await file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "画像が大きすぎます（10MBまで）")
        if not data:
            raise HTTPException(400, "画像が空です")
        t0 = time.perf_counter()
        try:
            img = load_image(data)
        except BadImage as e:
            raise HTTPException(400, str(e)) from None
        guesses = clf.top(img, 3)
        elapsed = int((time.perf_counter() - t0) * 1000)
        items = [{"label": g.label, "score": round(g.score, 4)} for g in guesses]
        category = judge(guesses)
        jid = db.add(hashlib.sha256(data).hexdigest(), category, items, elapsed)
        return {"id": jid, "category": category, "guesses": items, "elapsed_ms": elapsed}

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):                 # 中の情報（スタックトレース）は外に出さない
        return JSONResponse({"error": "うまく判定できませんでした。時間をおいてお試しください"}, status_code=500)

    return app
