"""Shared fixtures for mcp-genomics tests."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from mcp_genomics.api import NCBIClient
from mcp_genomics.data import CacheDB

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def gene_672_summary():
    """BRCA1 gene summary fixture."""
    with open(FIXTURES_DIR / "gene_672_summary.json") as f:
        return json.load(f)


@pytest.fixture
def gene_7157_summary():
    """TP53 gene summary fixture."""
    with open(FIXTURES_DIR / "gene_7157_summary.json") as f:
        return json.load(f)


@pytest.fixture
def pubmed_links():
    """PubMed elink response fixture for BRCA1."""
    with open(FIXTURES_DIR / "pubmed_brca1_links.json") as f:
        return json.load(f)


@pytest.fixture
def pubmed_summaries():
    """PubMed esummary response fixture."""
    with open(FIXTURES_DIR / "pubmed_summaries.json") as f:
        return json.load(f)


@pytest.fixture
def mock_client():
    """Create a mock NCBIClient with AsyncMock methods."""
    client = AsyncMock(spec=NCBIClient)
    return client


@pytest.fixture
def temp_cache():
    """Create a temporary CacheDB for testing (isolated from real cache)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_cache.db"
        cache = CacheDB(db_path=db_path)
        yield cache
        cache.close()
