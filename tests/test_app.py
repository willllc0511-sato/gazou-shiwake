"""画面と API のテスト。判定の正しさは本物のモデルで見る（test_model.py）。ここでは偽のモデルで、入力の扱いと守りを見る。"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.categories import category_of
from app.db import Store
from app.main import RateLimit, create_app
from app.model import Guess, judge


class FakeClassifier:
    def top(self, img, k=3):
        return [Guess("running shoe", 0.7), Guess("sandal", 0.2), Guess("sock", 0.05)]


def png(w=64, h=48, color=(200, 30, 30)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), color).save(b, "PNG")
    return b.getvalue()


@pytest.fixture
def client(tmp_path):
    app = create_app(FakeClassifier(), Store(f"sqlite:///{tmp_path}/t.db"), RateLimit(5))
    return TestClient(app)


def test_classify_returns_top3_and_category_and_is_recorded(client):
    r = client.post("/api/classify", files={"file": ("a.png", png(), "image/png")})
    assert r.status_code == 200
    d = r.json()
    assert d["category"] == "靴" and [g["label"] for g in d["guesses"]] == ["running shoe", "sandal", "sock"]
    h = client.get("/api/history").json()["items"]
    assert h[0]["id"] == d["id"] and h[0]["category"] == "靴"
    assert "a.png" not in str(h)                                             # ファイル名は残さない


@pytest.mark.parametrize("data,expect", [
    (b"", "画像が空です"),
    (b"not an image at all", "画像として読めませんでした"),
    (png()[:40], "画像として読めませんでした"),                                # 途中で切れた PNG
    (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "画像として読めませんでした"),
])
def test_bad_files_are_refused_in_japanese(client, data, expect):
    r = client.post("/api/classify", files={"file": ("x", data, "image/png")})
    assert r.status_code == 400 and expect in r.json()["error"]


def test_too_large_file_is_refused(client):
    r = client.post("/api/classify", files={"file": ("big.png", b"\0" * (10 * 1024 * 1024 + 1), "image/png")})
    assert r.status_code == 413 and "10MB" in r.json()["error"]


def test_decompression_bomb_is_refused(client):
    b = io.BytesIO()
    Image.new("1", (9000, 9000)).save(b, "PNG")                              # 8,100万画素（ファイルは小さいが展開すると大きい）
    r = client.post("/api/classify", files={"file": ("bomb.png", b.getvalue(), "image/png")})
    assert r.status_code == 400


def test_rate_limit_per_client(client):
    codes = [client.post("/api/classify", files={"file": ("a.png", png(), "image/png")}).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_forged_real_ip_from_outside_is_ignored():
    from app.main import client_ip

    class R:
        def __init__(self, host, real):
            self.client = type("C", (), {"host": host})()
            self.headers = {"x-real-ip": real}
    assert client_ip(R("203.0.113.5", "1.2.3.4")) == "203.0.113.5"            # 外から直接：偽のヘッダーは使わない
    assert client_ip(R("127.0.0.1", "1.2.3.4")) == "1.2.3.4"                  # 手前の nginx から


def test_security_headers_and_no_api_docs(client):
    r = client.get("/")
    assert r.status_code == 200 and "商品写真の仕分け" in r.text
    assert r.headers["x-content-type-options"] == "nosniff" and "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert client.get("/docs").status_code == 404 and client.get("/openapi.json").status_code == 404


def test_unexpected_error_does_not_leak_internals(tmp_path):
    class Boom:
        def top(self, img, k=3):
            raise RuntimeError("/srv/secret/path line 42")
    c = TestClient(create_app(Boom(), Store(f"sqlite:///{tmp_path}/t.db"), RateLimit(5)), raise_server_exceptions=False)
    r = c.post("/api/classify", files={"file": ("a.png", png(), "image/png")})
    assert r.status_code == 500 and "secret" not in r.text


def test_categories_match_whole_words():
    assert category_of("running shoe") == "靴"
    assert category_of("capuchin") == "その他"                                # cap（帽子）に当てない
    assert category_of("acorn") == "その他"                                   # corn に当てない
    assert category_of("laptop") == "電子機器" and category_of("banana") == "食品" and category_of("coffee mug") == "台所用品"


def test_judge_needs_enough_confidence():
    assert judge([Guess("banana", 0.9), Guess("lemon", 0.05), Guess("fig", 0.01)]) == "食品"
    assert judge([Guess("banana", 0.1), Guess("laptop", 0.05), Guess("sock", 0.04)]) == "要確認"
