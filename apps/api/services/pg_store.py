import os
from contextlib import contextmanager
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "")


@contextmanager
def _conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_tables() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    author TEXT NOT NULL,
                    content TEXT NOT NULL,
                    title TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY,
                    slug TEXT NOT NULL,
                    author TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    tags TEXT,
                    cover_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)


def count_rows(table: str) -> int:
    if table not in ("messages", "posts"):
        raise ValueError(f"unknown table: {table}")
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            return cur.fetchone()[0]


def insert_message(item: dict[str, Any]) -> None:
    insert_messages([item])


def insert_messages(items: list[dict[str, Any]]) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO messages (id, author, content, title, created_at)
                   VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                [(it["id"], it["author"], it["content"], it.get("title"), it["created_at"]) for it in items],
            )


def list_messages(limit: int | None = 20) -> list[dict[str, Any]]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(row) for row in cur.fetchall()]


def insert_post(item: dict[str, Any]) -> None:
    insert_posts([item])


def insert_posts(items: list[dict[str, Any]]) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO posts
                   (id, slug, author, title, body, tags, cover_url, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING""",
                [
                    (
                        it["id"], it["slug"], it["author"], it["title"], it["body"],
                        it.get("tags"), it.get("cover_url"), it["created_at"], it["updated_at"],
                    )
                    for it in items
                ],
            )


def list_posts(limit: int | None = 50) -> list[dict[str, Any]]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(row) for row in cur.fetchall()]
