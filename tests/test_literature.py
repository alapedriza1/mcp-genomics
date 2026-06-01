"""Tests for the get_literature tool."""

import pytest

from mcp_genomics.tools.literature import get_literature


@pytest.mark.asyncio
async def test_literature_returns_articles(mock_client, temp_cache):
    """Given fixtures for elink + pubmed esummary, assert output contains articles."""
    mock_client.elink.return_value = ["18500671", "18647968", "18594935"]
    mock_client.esummary.return_value = [
        {
            "uid": "18500671",
            "pubdate": "2009 May",
            "source": "Breast Cancer Res Treat",
            "title": "A common Greenlandic Inuit BRCA1 RING domain founder mutation.",
            "authors": [
                {"name": "Hansen TV"},
                {"name": "Ejlertsen B"},
                {"name": "Albrechtsen A"},
                {"name": "Bergsten E"},
            ],
            "volume": "115",
            "pages": "69-76",
        },
        {
            "uid": "18647968",
            "pubdate": "2008 Dec",
            "source": "Oncogene",
            "title": "Aberrant subcellular localization of BRCA1 in breast cancer.",
            "authors": [{"name": "Chen Y"}, {"name": "Chen CF"}],
            "volume": "27",
            "pages": "5081-5091",
        },
        {
            "uid": "18594935",
            "pubdate": "2008 Jul 2",
            "source": "J Natl Cancer Inst",
            "title": "BRCA1 promoter methylation in peripheral blood DNA of mutation negative familial breast cancer patients.",
            "authors": [{"name": "Bentley DR"}, {"name": "Balasubramanian S"}, {"name": "Swerdlow HP"}],
            "volume": "100",
            "pages": "941-949",
        },
    ]

    result = await get_literature(mock_client, temp_cache, "672", max_results=5)

    assert result["gene_id"] == "672"
    assert result["total_linked_articles"] == 3
    assert len(result["articles"]) == 3

    article = result["articles"][0]
    assert article["pmid"] == "18500671"
    assert article["title"] == "A common Greenlandic Inuit BRCA1 RING domain founder mutation."
    assert article["journal"] == "Breast Cancer Res Treat"
    assert article["pub_date"] == "2009 May"
    assert "pubmed.ncbi.nlm.nih.gov/18500671" in article["pubmed_url"]

    # Authors with >3 should have "et al."
    assert "et al." in article["authors"]


@pytest.mark.asyncio
async def test_literature_no_articles(mock_client, temp_cache):
    """Given empty elink response, assert clear message."""
    mock_client.elink.return_value = []

    result = await get_literature(mock_client, temp_cache, "672")

    assert result["articles"] == []
    assert result["total_linked_articles"] == 0
    assert "message" in result
    assert "No PubMed articles" in result["message"]


@pytest.mark.asyncio
async def test_literature_uses_cache(mock_client, temp_cache):
    """Call twice, assert second call uses cache."""
    mock_client.elink.return_value = ["18500671"]
    mock_client.esummary.return_value = [
        {
            "uid": "18500671",
            "pubdate": "2009 May",
            "source": "Breast Cancer Res Treat",
            "title": "A common Greenlandic Inuit BRCA1 RING domain founder mutation.",
            "authors": [{"name": "Hansen TV"}],
            "volume": "115",
            "pages": "69-76",
        },
    ]

    # First call
    result1 = await get_literature(mock_client, temp_cache, "672")
    assert result1["cached"] is False

    # Second call — should use cache
    result2 = await get_literature(mock_client, temp_cache, "672")
    assert result2["cached"] is True
    assert mock_client.elink.call_count == 1


@pytest.mark.asyncio
async def test_literature_two_authors_no_et_al(mock_client, temp_cache):
    """Assert that <=3 authors are listed without et al."""
    mock_client.elink.return_value = ["18647968"]
    mock_client.esummary.return_value = [
        {
            "uid": "18647968",
            "pubdate": "2008 Dec",
            "source": "Oncogene",
            "title": "Test article",
            "authors": [{"name": "Chen Y"}, {"name": "Chen CF"}],
            "volume": "27",
            "pages": "5081-5091",
        },
    ]

    result = await get_literature(mock_client, temp_cache, "18647968")

    article = result["articles"][0]
    assert "et al." not in article["authors"]
    assert "Chen Y" in article["authors"]
    assert "Chen CF" in article["authors"]
