"""Tests for the compare_genes tool."""

import pytest

from mcp_genomics.tools.compare_genes import compare_genes


@pytest.mark.asyncio
async def test_compare_two_genes(mock_client, temp_cache, gene_672_summary, gene_7157_summary):
    """Given fixtures for genes 672 and 7157, assert comparison table has correct structure."""
    mock_client.esummary.side_effect = [[gene_672_summary], [gene_7157_summary]]
    mock_client.efetch_xml.return_value = "<Entrezgene-Set></Entrezgene-Set>"

    result = await compare_genes(mock_client, temp_cache, ["672", "7157"])

    assert result["genes_compared"] == 2
    assert len(result["comparison_table"]) > 0
    assert "per_gene_details" in result
    assert "BRCA1" in result["per_gene_details"]
    assert "TP53" in result["per_gene_details"]

    # Check comparison table structure
    fields = [row["field"] for row in result["comparison_table"]]
    assert "symbol" in fields
    assert "chromosome" in fields
    assert "gene_type" in fields


@pytest.mark.asyncio
async def test_compare_identifies_shared_chromosome(
    mock_client, temp_cache, gene_672_summary, gene_7157_summary
):
    """BRCA1 and TP53 are both on chromosome 17, assert this is detected."""
    mock_client.esummary.side_effect = [[gene_672_summary], [gene_7157_summary]]
    mock_client.efetch_xml.return_value = "<Entrezgene-Set></Entrezgene-Set>"

    result = await compare_genes(mock_client, temp_cache, ["672", "7157"])

    overlap = result["overlap_analysis"]
    assert overlap["chromosome_co_location"]["same_chromosome"] is True
    assert "17" in overlap["chromosome_co_location"]["details"]
    assert "BRCA1" in overlap["chromosome_co_location"]["details"]
    assert "TP53" in overlap["chromosome_co_location"]["details"]


@pytest.mark.asyncio
async def test_compare_minimum_two(mock_client, temp_cache):
    """Assert error when only one gene ID provided."""
    result = await compare_genes(mock_client, temp_cache, ["672"])

    assert "error" in result
    assert "At least 2" in result["error"]


@pytest.mark.asyncio
async def test_compare_maximum_five(mock_client, temp_cache):
    """Assert error when more than 5 gene IDs provided."""
    result = await compare_genes(mock_client, temp_cache, ["1", "2", "3", "4", "5", "6"])

    assert "error" in result
    assert "Maximum 5" in result["error"]
