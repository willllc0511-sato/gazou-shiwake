"""判定の履歴をデータベースに残す。本番は PostgreSQL（DATABASE_URL）、テストと手元は SQLite。
画像そのものとファイル名は保存しない（写真に個人の情報が写っていることがあるため）。照合用のハッシュ値と結果だけ残す。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, Table, Text, create_engine, desc, insert, select

metadata = MetaData()
judgements = Table(
    "judgements", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime(timezone=True), nullable=False, index=True),
    Column("sha256", String(64), nullable=False, index=True),     # 同じ写真が何度来たかを数えられる
    Column("category", String(32), nullable=False),
    Column("top_label", String(128), nullable=False),
    Column("top_score", Float, nullable=False),
    Column("guesses", Text, nullable=False),                      # 上位3件（JSON）
    Column("elapsed_ms", Integer, nullable=False),
)


def read_url() -> str:
    """DATABASE_URL_FILE（Docker の secrets。パスワードを環境変数や設定ファイルに書かない）→ DATABASE_URL → 手元の SQLite"""
    f = os.environ.get("DATABASE_URL_FILE")
    if f:
        return open(f, encoding="utf-8").read().strip()
    return os.environ.get("DATABASE_URL") or "sqlite:///./judgements.db"


class Store:
    def __init__(self, url: str | None = None):
        url = url or read_url()
        self.engine = create_engine(url, pool_pre_ping=True, future=True)
        metadata.create_all(self.engine)

    def add(self, sha256: str, category: str, guesses: list[dict], elapsed_ms: int) -> int:
        with self.engine.begin() as c:
            r = c.execute(insert(judgements).values(
                created_at=datetime.now(timezone.utc), sha256=sha256, category=category,
                top_label=guesses[0]["label"], top_score=guesses[0]["score"],
                guesses=json.dumps(guesses, ensure_ascii=False), elapsed_ms=elapsed_ms))
            return int(r.inserted_primary_key[0])

    def recent(self, limit: int = 20) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(select(judgements).order_by(desc(judgements.c.id)).limit(limit)).mappings().all()
        return [{"id": r["id"], "created_at": r["created_at"].isoformat(), "category": r["category"],
                 "top_label": r["top_label"], "top_score": round(r["top_score"], 4), "elapsed_ms": r["elapsed_ms"]} for r in rows]
