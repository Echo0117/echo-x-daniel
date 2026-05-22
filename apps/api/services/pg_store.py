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


def insert_message(item: dict[str, Any]) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (id, author, content, title, created_at) VALUES (%s, %s, %s, %s, %s)",
                (item["id"], item["author"], item["content"], item.get("title"), item["created_at"]),
            )


def list_messages(limit: int = 20) -> list[dict[str, Any]]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(row) for row in cur.fetchall()]


def insert_post(item: dict[str, Any]) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO posts
                   (id, slug, author, title, body, tags, cover_url, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    item["id"], item["slug"], item["author"], item["title"], item["body"],
                    item.get("tags"), item.get("cover_url"), item["created_at"], item["updated_at"],
                ),
            )


def list_posts(limit: int = 50) -> list[dict[str, Any]]:
    with _conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(row) for row in cur.fetchall()]
