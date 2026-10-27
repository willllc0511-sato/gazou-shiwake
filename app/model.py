"""画像認識：公開の学習済みモデル（ONNX Model Zoo の MobileNetV2・ImageNet 1000分類）を CPU で動かす。
外部の AI サービスは使わないので、1枚ごとの利用料はかからない。"""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from .categories import category_of

MODEL_DIR = Path(__file__).resolve().parent.parent / "model"
MAX_PIXELS = 40_000_000          # 細工した巨大画像（展開すると何GBにもなるもの）で止まらないように
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class BadImage(ValueError):
    """画像として読めない・大きすぎる。メッセージはそのまま画面に出す"""


@dataclass
class Guess:
    label: str
    score: float


def load_image(data: bytes) -> Image.Image:
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()                                   # 壊れたファイルをここで落とす
        img = Image.open(io.BytesIO(data))
        if img.width * img.height > MAX_PIXELS:
            raise BadImage("画像が大きすぎます（4,000万画素まで）")
        return img.convert("RGB")
    except BadImage:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as e:
        raise BadImage("画像として読めませんでした（JPEG・PNG・WebP の写真を選んでください）") from e


def preprocess(img: Image.Image) -> np.ndarray:
    """短い辺を256にして中央224を切り出し、学習時と同じ正規化をする（1×3×224×224）"""
    w, h = img.size
    s = 256 / min(w, h)
    img = img.resize((max(224, round(w * s)), max(224, round(h * s))), Image.BILINEAR)
    w, h = img.size
    left, top = (w - 224) // 2, (h - 224) // 2
    a = np.asarray(img.crop((left, top, left + 224, top + 224)), dtype=np.float32) / 255.0
    a = (a - MEAN) / STD
    return a.transpose(2, 0, 1)[None, ...]


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max())
    return e / e.sum()


class Classifier:
    def __init__(self, model_dir: Path = MODEL_DIR):
        import onnxruntime as ort
        self.labels = (model_dir / "imagenet_classes.txt").read_text(encoding="utf-8").splitlines()
        if len(self.labels) != 1000:
            raise RuntimeError(f"分類名の一覧が1000件ではありません（{len(self.labels)}件）")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(model_dir / "mobilenetv2-12.onnx"), opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def top(self, img: Image.Image, k: int = 3) -> list[Guess]:
        out = self.session.run(None, {self.input_name: preprocess(img)})[0][0]
        p = softmax(out)
        idx = np.argsort(p)[::-1][:k]
        return [Guess(self.labels[i], float(p[i])) for i in idx]


def judge(guesses: list[Guess]) -> str:
    """上位3件の確からしさを、仕分け先ごとに足して一番多いところへ振り分ける"""
    total: dict[str, float] = {}
    for g in guesses:
        c = category_of(g.label)
        total[c] = total.get(c, 0.0) + g.score
    best = max(total, key=total.get)
    return best if total[best] >= 0.2 else "要確認"
