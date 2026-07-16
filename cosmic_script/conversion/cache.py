"""Content-hash LLM response cache using SQLite.

Provides a thread-safe, TTL-aware cache that maps SHA256 hashes of
(chapter_text, model, temperature, system_prompt_hash) to LLM responses.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default cache directory under user home
_DEFAULT_CACHE_DIR = Path.home() / ".cosmic-script"
_DEFAULT_DB_PATH = _DEFAULT_CACHE_DIR / "cache.db"

# Default TTL: 24 hours in seconds
_DEFAULT_TTL_SECONDS = 86400

# Schema for the cache table
_CACHE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key TEXT PRIMARY KEY,
    response TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    hit_count INTEGER DEFAULT 0
)"""


class ConversionCache:
    """Content-hash LLM response cache backed by SQLite.

    Cache keys are SHA256 hashes of ``{chapter_text}|{model}|{temperature}|
    {system_prompt_hash}``.  Entries expire after *ttl_seconds* (default 24 h).

    Thread-safe via ``check_same_thread=False``.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        ttl_seconds: int = 86400,
        enabled: bool = True,
    ) -> None:
        """Initialise the cache.

        Args:
            db_path: Path to the SQLite database file.  Defaults to
                ``~/.cosmic-script/cache.db``.
            ttl_seconds: Entry time-to-live in seconds (default 86400 = 24 h).
            enabled: If False, all operations are no-ops.
        """
        self._enabled = enabled
        self._ttl = ttl_seconds
        self._db_path = str(db_path) if (
            db_path is not None
        ) else str(_DEFAULT_DB_PATH)

        if not enabled:
            logger.info("ConversionCache is disabled")
            self._conn: sqlite3.Connection | None = None
            return

        # Ensure parent directory exists
        parent = Path(self._db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
        )
        self._conn.execute(_CACHE_SCHEMA)
        self._conn.commit()
        logger.info("ConversionCache initialised at %s", self._db_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, cache_key: str) -> Optional[str]:
        """Retrieve a cached response by key.

        Returns None if the key is not found, the entry is expired, or
        caching is disabled.

        Args:
            cache_key: The SHA256 hash key to look up.

        Returns:
            The cached response text, or None.
        """
        if not self._enabled or self._conn is None:
            return None

        try:
            row = self._conn.execute(
                """SELECT response, created_at FROM llm_cache
                   WHERE cache_key = ?""",
                (cache_key,),
            ).fetchone()
        except sqlite3.Error:
            logger.exception("Cache read error")
            return None

        if row is None:
            return None

        response, created_at = row

        # Check TTL
        try:
            created_ts = _parse_timestamp(created_at)
            if time.time() - created_ts > self._ttl:
                logger.info("Cache entry expired for key %s...", cache_key[:12])
                self._delete(cache_key)
                return None
        except (ValueError, TypeError):
            # If timestamp is unparseable, treat as expired
            self._delete(cache_key)
            return None

        # Increment hit count
        try:
            self._conn.execute(
                "UPDATE llm_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (cache_key,),
            )
            self._conn.commit()
        except sqlite3.Error:
            pass

        logger.info("Cache HIT for key %s...", cache_key[:12])
        return response

    def set(self, cache_key: str, response: str, model: str) -> None:
        """Store a response in the cache.

        Args:
            cache_key: The SHA256 hash key.
            response: The LLM response text to cache.
            model: The model identifier used to generate the response.
        """
        if not self._enabled or self._conn is None:
            return

        try:
            self._conn.execute(
                """INSERT OR REPLACE INTO llm_cache
                   (cache_key, response, model, created_at, hit_count)
                   VALUES (?, ?, ?, datetime('now'), 0)""",
                (cache_key, response, model),
            )
            self._conn.commit()
        except sqlite3.Error:
            logger.exception("Cache write error")

    def clear(self) -> None:
        """Delete all entries from the cache."""
        if not self._enabled or self._conn is None:
            return
        try:
            self._conn.execute("DELETE FROM llm_cache")
            self._conn.commit()
            logger.info("Cache cleared")
        except sqlite3.Error:
            logger.exception("Cache clear error")

    def stats(self) -> dict:
        """Return cache statistics.

        Returns:
            A dict with keys: total_entries, total_hits, oldest_entry,
            newest_entry.
        """
        if not self._enabled or self._conn is None:
            return {"total_entries": 0, "total_hits": 0}

        try:
            row = self._conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(hit_count), 0) FROM llm_cache"
            ).fetchone()
            total = row[0] if row else 0
            hits = row[1] if row else 0
            return {"total_entries": total, "total_hits": hits}
        except sqlite3.Error:
            logger.exception("Cache stats error")
            return {"total_entries": 0, "total_hits": 0}

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._conn = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _delete(self, cache_key: str) -> None:
        """Delete a single cache entry."""
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "DELETE FROM llm_cache WHERE cache_key = ?",
                (cache_key,),
            )
            self._conn.commit()
        except sqlite3.Error:
            pass


def _build_cache_key(
    chapter_text: str,
    model: str,
    temperature: float,
    system_prompt: str,
) -> str:
    """Build a SHA256 cache key from conversion parameters.

    Args:
        chapter_text: The chapter text being converted.
        model: The LLM model identifier.
        temperature: The LLM sampling temperature.
        system_prompt: The full system prompt text.

    Returns:
        A hex-encoded SHA256 digest.
    """
    raw = f"{chapter_text}|{model}|{temperature}|{_hash_str(system_prompt)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hash_str(text: str) -> str:
    """Return a SHA256 hex digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_timestamp(ts_str: str) -> float:
    """Parse a SQLite datetime string into a Unix timestamp (UTC).

    SQLite ``datetime('now')`` returns UTC time.  We parse it as a naive
    datetime and treat it as UTC to produce a correct Unix timestamp.

    Args:
        ts_str: A datetime string from SQLite.

    Returns:
        Unix timestamp as a float.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    from datetime import datetime as _dt, timezone as _tz

    # SQLite datetime format: YYYY-MM-DD HH:MM:SS (UTC)
    naive = _dt.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=_tz.utc).timestamp()

