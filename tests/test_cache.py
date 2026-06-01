"""Tests for the SQLite caching layer."""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mcp_genomics.data.cache import CacheDB, GENE_CACHE_TTL, LITERATURE_CACHE_TTL


class TestGeneCacheOperations:
    """Tests for gene cache insert, retrieve, and expiry."""

    def test_set_and_get_gene(self, temp_cache):
        """Test basic set and get for gene cache."""
        data = {"gene_id": "672", "symbol": "BRCA1", "full_name": "BRCA1 DNA repair associated"}
        temp_cache.set_gene("672", data)

        result = temp_cache.get_gene("672")
        assert result is not None
        assert result["gene_id"] == "672"
        assert result["symbol"] == "BRCA1"

    def test_get_gene_miss(self, temp_cache):
        """Test cache miss returns None."""
        result = temp_cache.get_gene("nonexistent")
        assert result is None

    def test_gene_cache_overwrite(self, temp_cache):
        """Test that setting the same gene_id overwrites."""
        temp_cache.set_gene("672", {"symbol": "OLD"})
        temp_cache.set_gene("672", {"symbol": "NEW"})

        result = temp_cache.get_gene("672")
        assert result["symbol"] == "NEW"

    def test_gene_cache_expiry(self, temp_cache):
        """Test that expired entries return None and are deleted."""
        temp_cache.set_gene("672", {"symbol": "BRCA1"})

        # Manually expire the entry by setting expires_at in the past
        expired_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        temp_cache._conn.execute(
            "UPDATE gene_cache SET expires_at = ? WHERE gene_id = ?",
            (expired_time, "672"),
        )
        temp_cache._conn.commit()

        result = temp_cache.get_gene("672")
        assert result is None


class TestLiteratureCacheOperations:
    """Tests for literature cache insert, retrieve, and expiry."""

    def test_set_and_get_literature(self, temp_cache):
        """Test basic set and get for literature cache."""
        data = [{"pmid": "123", "title": "Test article"}]
        temp_cache.set_literature("672", data)

        result = temp_cache.get_literature("672")
        assert result is not None
        assert len(result) == 1
        assert result[0]["pmid"] == "123"

    def test_get_literature_miss(self, temp_cache):
        """Test cache miss returns None."""
        result = temp_cache.get_literature("nonexistent")
        assert result is None

    def test_literature_cache_expiry(self, temp_cache):
        """Test that expired literature entries return None."""
        temp_cache.set_literature("672", [{"pmid": "123"}])

        # Manually expire
        expired_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        temp_cache._conn.execute(
            "UPDATE literature_cache SET expires_at = ? WHERE gene_id = ?",
            (expired_time, "672"),
        )
        temp_cache._conn.commit()

        result = temp_cache.get_literature("672")
        assert result is None


class TestCacheMaintenance:
    """Tests for cache maintenance operations."""

    def test_clear_all(self, temp_cache):
        """Test that clear_all removes all entries."""
        temp_cache.set_gene("672", {"symbol": "BRCA1"})
        temp_cache.set_gene("7157", {"symbol": "TP53"})
        temp_cache.set_literature("672", [{"pmid": "123"}])

        temp_cache.clear_all()

        assert temp_cache.get_gene("672") is None
        assert temp_cache.get_gene("7157") is None
        assert temp_cache.get_literature("672") is None

    def test_purge_expired(self, temp_cache):
        """Test that purge_expired removes only stale entries."""
        # Add a valid entry
        temp_cache.set_gene("672", {"symbol": "BRCA1"})

        # Add an expired entry
        temp_cache.set_gene("7157", {"symbol": "TP53"})
        expired_time = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        temp_cache._conn.execute(
            "UPDATE gene_cache SET expires_at = ? WHERE gene_id = ?",
            (expired_time, "7157"),
        )
        temp_cache._conn.commit()

        deleted = temp_cache.purge_expired()

        assert deleted == 1
        assert temp_cache.get_gene("672") is not None
        assert temp_cache.get_gene("7157") is None
