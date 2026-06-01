"""Tests for the get_gene_details tool."""

import pytest

from mcp_genomics.tools.gene_details import get_gene_details


@pytest.mark.asyncio
async def test_details_returns_full_profile(mock_client, temp_cache, gene_672_summary):
    """Given fixture for gene 672, assert all fields are present."""
    mock_client.esummary.return_value = [gene_672_summary]
    mock_client.efetch_xml.return_value = "<Entrezgene-Set></Entrezgene-Set>"

    result = await get_gene_details(mock_client, temp_cache, "672")

    assert result["gene_id"] == "672"
    assert result["symbol"] == "BRCA1"
    assert result["full_name"] == "BRCA1 DNA repair associated"
    assert result["organism"] == "Homo sapiens"
    assert result["chromosome"] == "17"
    assert result["map_location"] == "17q21.31"
    assert result["gene_type"] == "genomic"
    assert "tumor suppressor" in result["summary"]
    assert "BRCAI" in result["aliases"]
    assert "RNF53" in result["aliases"]
    assert "FANCS" in result["aliases"]
    assert result["cached"] is False
    assert "retrieved_at" in result


@pytest.mark.asyncio
async def test_details_uses_cache(mock_client, temp_cache, gene_672_summary):
    """Call twice, assert second call doesn't hit the API mock."""
    mock_client.esummary.return_value = [gene_672_summary]
    mock_client.efetch_xml.return_value = "<Entrezgene-Set></Entrezgene-Set>"

    # First call — hits API
    result1 = await get_gene_details(mock_client, temp_cache, "672")
    assert result1["cached"] is False

    # Second call — should use cache
    result2 = await get_gene_details(mock_client, temp_cache, "672")
    assert result2["cached"] is True

    # esummary should only have been called once
    assert mock_client.esummary.call_count == 1


@pytest.mark.asyncio
async def test_details_invalid_id(mock_client, temp_cache):
    """Assert a clear error for a nonexistent gene ID."""
    mock_client.esummary.return_value = []

    result = await get_gene_details(mock_client, temp_cache, "9999999999")

    assert "error" in result
    assert "not found" in result["error"]
    assert result["gene_id"] == "9999999999"


@pytest.mark.asyncio
async def test_details_xml_enrichment_non_fatal(mock_client, temp_cache, gene_672_summary):
    """Assert that if efetch_xml fails, the tool still returns esummary data."""
    mock_client.esummary.return_value = [gene_672_summary]
    mock_client.efetch_xml.side_effect = Exception("XML fetch failed")

    result = await get_gene_details(mock_client, temp_cache, "672")

    # Should still succeed with basic data
    assert result["gene_id"] == "672"
    assert result["symbol"] == "BRCA1"
    # Diseases and pathways will be empty since XML failed
    assert result["diseases"] == []
    assert result["pathways"] == []
