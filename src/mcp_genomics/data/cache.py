"""
SQLite caching layer for NCBI API responses.

Caches gene details (7-day TTL) and literature results (1-day TTL)
to avoid redundant API calls within multi-tool prompt workflows.

Cache location: ~/.mcp-genomics/cache.db
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default cache directory
CACHE_DIR = Path.home() / ".mcp-genomics"
CACHE_DB_PATH = CACHE_DIR / "cache.db"

# TTL durations
GENE_CACHE_TTL = timedelta(days=7)
LITERATURE_CACHE_TTL = timedelta(days=1)


class CacheDB:
    """
    SQLite-backed response cache with domain-specific tables.

    Provides separate caching for gene details and literature results,
    each with its own TTL. Expired entries are lazily evicted on read
    and can be bulk-purged via purge_expired().

    Tables:
        gene_cache       — gene detail records, 7-day TTL
        literature_cache — PubMed literature per gene, 1-day TTL

    Usage:
        cache = CacheDB()
        cache.get_gene("672")  # returns dict or None
        cache.set_gene("672", {"name": "BRCA1", ...})
        cache.close()
    """

    def __init__(self, db_path: Path = CACHE_DB_PATH):
        """
        Initialise the cache database.

        Creates the cache directory and SQLite file if they don't exist,
        then ensures the required tables are present.

        Args:
            db_path: Path to the SQLite database file.
                     Defaults to ~/.mcp-genomics/cache.db.
        """
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Create the database connection and ensure tables exist."""
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS gene_cache (
                gene_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS literature_cache (
                gene_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)
        self._conn.commit()

    @staticmethod
    def _now() -> datetime:
        """Return the current UTC datetime."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _is_expired(expires_at: str) -> bool:
        """
        Check if an ISO 8601 expiry timestamp has passed.

        Args:
            expires_at: ISO 8601 formatted expiry timestamp string.

        Returns:
            True if the current time is past the expiry, False otherwise.
        """
        expiry = datetime.fromisoformat(expires_at)
        return datetime.now(timezone.utc) > expiry

    # ─── Gene Cache ───────────────────────────────────────────────────────

    def get_gene(self, gene_id: str) -> dict[str, Any] | None:
        """
        Retrieve cached gene details if not expired.

        If the entry exists but has expired, it is deleted from the
        database and None is returned.

        Args:
            gene_id: NCBI Gene UID (e.g., "672" for BRCA1).

        Returns:
            Parsed gene data dict if cached and valid, None otherwise.
        """
        cursor = self._conn.execute(
            "SELECT data, expires_at FROM gene_cache WHERE gene_id = ?",
            (gene_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        data, expires_at = row
        if self._is_expired(expires_at):
            self._conn.execute(
                "DELETE FROM gene_cache WHERE gene_id = ?", (gene_id,)
            )
            self._conn.commit()
            logger.debug("Gene cache expired for %s", gene_id)
            return None

        logger.debug("Gene cache hit for %s", gene_id)
        return json.loads(data)

    def set_gene(self, gene_id: str, data: dict[str, Any]) -> None:
        """
        Cache gene details with a 7-day TTL.

        Overwrites any existing entry for the same gene_id.

        Args:
            gene_id: NCBI Gene UID (e.g., "672" for BRCA1).
            data: Gene detail dict as returned by the NCBI esummary endpoint.
        """
        now = self._now()
        expires = now + GENE_CACHE_TTL
        self._conn.execute(
            "INSERT OR REPLACE INTO gene_cache (gene_id, data, retrieved_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (gene_id, json.dumps(data), now.isoformat(), expires.isoformat()),
        )
        self._conn.commit()

    # ─── Literature Cache ─────────────────────────────────────────────────

    def get_literature(self, gene_id: str) -> list[dict[str, Any]] | None:
        """
        Retrieve cached literature results if not expired.

        If the entry exists but has expired, it is deleted from the
        database and None is returned.

        Args:
            gene_id: NCBI Gene UID whose linked PubMed articles are cached.

        Returns:
            List of PubMed article summary dicts if cached and valid,
            None otherwise.
        """
        cursor = self._conn.execute(
            "SELECT data, expires_at FROM literature_cache WHERE gene_id = ?",
            (gene_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        data, expires_at = row
        if self._is_expired(expires_at):
            self._conn.execute(
                "DELETE FROM literature_cache WHERE gene_id = ?", (gene_id,)
            )
            self._conn.commit()
            logger.debug("Literature cache expired for %s", gene_id)
            return None

        logger.debug("Literature cache hit for %s", gene_id)
        return json.loads(data)

    def set_literature(self, gene_id: str, data: list[dict[str, Any]]) -> None:
        """
        Cache literature results with a 1-day TTL.

        Overwrites any existing entry for the same gene_id.

        Args:
            gene_id: NCBI Gene UID whose linked PubMed articles are being cached.
            data: List of PubMed article summary dicts as returned by esummary.
        """
        now = self._now()
        expires = now + LITERATURE_CACHE_TTL
        self._conn.execute(
            "INSERT OR REPLACE INTO literature_cache (gene_id, data, retrieved_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (gene_id, json.dumps(data), now.isoformat(), expires.isoformat()),
        )
        self._conn.commit()

    # ─── Maintenance ──────────────────────────────────────────────────────

    def clear_all(self) -> None:
        """
        Clear all cached entries from both tables.

        Use for debugging or when a user wants to force-refresh all data.
        """
        self._conn.execute("DELETE FROM gene_cache")
        self._conn.execute("DELETE FROM literature_cache")
        self._conn.commit()

    def purge_expired(self) -> int:
        """
        Remove all expired entries from both tables.

        Intended to be called on server startup to keep the database
        lean without relying solely on lazy eviction during reads.

        Returns:
            Total number of expired rows deleted across both tables.
        """
        now = self._now().isoformat()
        c1 = self._conn.execute(
            "DELETE FROM gene_cache WHERE expires_at < ?", (now,)
        )
        c2 = self._conn.execute(
            "DELETE FROM literature_cache WHERE expires_at < ?", (now,)
        )
        self._conn.commit()
        total = c1.rowcount + c2.rowcount
        if total:
            logger.info("Purged %d expired cache entries", total)
        return total

    def close(self) -> None:
        """
        Close the database connection.

        Should be called during server shutdown to release the SQLite file
        handle cleanly. Safe to call multiple times.
        """
        if self._conn:
            self._conn.close()
            self._conn = None
