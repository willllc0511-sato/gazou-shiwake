"""本物のモデルで判定する（モデルのファイルがある時だけ。Docker の中では必ずある）"""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.model import MODEL_DIR, Classifier

pytestmark = pytest.mark.skipif(not (MODEL_DIR / "mobilenetv2-12.onnx").exists(), reason="モデルのファイルが無い")
SAMPLES = Path(__file__).resolve().parent / "samples"


@pytest.fixture(scope="module")
def clf():
    return Classifier()


def test_returns_three_scores_that_add_up_below_one(clf):
    img = Image.new("RGB", (640, 480), (240, 240, 240))
    ImageDraw.Draw(img).ellipse((200, 120, 440, 360), fill=(250, 200, 30))
    g = clf.top(img, 3)
    assert len(g) == 3 and g[0].score >= g[1].score >= g[2].score and sum(x.score for x in g) <= 1.0001


def test_judges_within_3_seconds_on_cpu(clf):
    img = Image.new("RGB", (4000, 3000), (120, 160, 200))                    # スマホの写真くらいの大きさ
    t0 = time.perf_counter()
    clf.top(img, 3)
    assert time.perf_counter() - t0 < 3


@pytest.mark.parametrize("name,expect", [("banana.jpg", "banana"), ("mug.jpg", "mug")])
def test_real_photos(clf, name, expect):
    p = SAMPLES / name
    if not p.exists():
        pytest.skip("見本の写真が無い")
    labels = [g.label.lower() for g in clf.top(Image.open(p).convert("RGB"), 3)]
    assert any(expect in l for l in labels), labels
