"""Tests for the search_genes tool."""

import pytest

from mcp_genomics.tools.search_genes import search_genes


@pytest.mark.asyncio
async def test_search_returns_structured_results(mock_client, gene_672_summary):
    """Given a fixture esearch + esummary response, assert output has correct structure."""
    mock_client.esearch.return_value = {
        "count": "1",
        "idlist": ["672"],
        "querytranslation": "BRCA1 AND human[orgn]",
    }
    mock_client.esummary.return_value = [gene_672_summary]

    result = await search_genes(mock_client, "BRCA1", "human", 10)

    assert result["total_found"] == 1
    assert len(result["results"]) == 1

    gene = result["results"][0]
    assert gene["gene_id"] == "672"
    assert gene["symbol"] == "BRCA1"
    assert gene["name"] == "BRCA1 DNA repair associated"
    assert gene["organism"] == "Homo sapiens"
    assert gene["chromosome"] == "17"
    assert gene["map_location"] == "17q21.31"
    assert "summary_snippet" in gene
    # Real summary is long enough to produce a snippet with "..."
    assert gene["summary_snippet"].endswith("...")


@pytest.mark.asyncio
async def test_search_no_results(mock_client):
    """Given an empty esearch response, assert output contains a clear no-results message."""
    mock_client.esearch.return_value = {
        "count": "0",
        "idlist": [],
        "querytranslation": "nonexistentgene AND human[orgn]",
    }

    result = await search_genes(mock_client, "nonexistentgene", "human", 10)

    assert result["total_found"] == 0
    assert result["results"] == []
    assert "message" in result
    assert "No genes found" in result["message"]


@pytest.mark.asyncio
async def test_search_clamps_max_results(mock_client, gene_672_summary):
    """Assert that max_results > 50 gets clamped to 50."""
    mock_client.esearch.return_value = {
        "count": "1",
        "idlist": ["672"],
    }
    mock_client.esummary.return_value = [gene_672_summary]

    result = await search_genes(mock_client, "BRCA1", "human", 100)

    assert result["clamped"] is True
    # Verify esearch was called with retmax=50
    mock_client.esearch.assert_called_once_with("gene", "BRCA1 AND human[orgn]", retmax=50)


@pytest.mark.asyncio
async def test_search_builds_organism_filter(mock_client, gene_672_summary):
    """Assert the search term includes the organism filter."""
    mock_client.esearch.return_value = {"count": "1", "idlist": ["672"]}
    mock_client.esummary.return_value = [gene_672_summary]

    await search_genes(mock_client, "BRCA1", "mouse", 10)

    mock_client.esearch.assert_called_once_with("gene", "BRCA1 AND mouse[orgn]", retmax=10)


@pytest.mark.asyncio
async def test_search_no_clamping_under_50(mock_client, gene_672_summary):
    """Assert that max_results <= 50 is not clamped."""
    mock_client.esearch.return_value = {"count": "1", "idlist": ["672"]}
    mock_client.esummary.return_value = [gene_672_summary]

    result = await search_genes(mock_client, "BRCA1", "human", 25)

    assert result.get("clamped", False) is False
    mock_client.esearch.assert_called_once_with("gene", "BRCA1 AND human[orgn]", retmax=25)
