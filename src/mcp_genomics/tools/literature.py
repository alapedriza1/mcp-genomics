"""
MCP tool: get_literature

Retrieve recent PubMed publications linked to a gene.
Grounds Claude's analysis in real, citable evidence.

Enterprise use case:
    "What's been published on KRAS recently? I need to know if
    there's new evidence before our R&D pipeline review."
"""

import logging
from typing import Any

from mcp_genomics.api import NCBIClient, NCBIClientError
from mcp_genomics.data import CacheDB

logger = logging.getLogger(__name__)

PUBMED_BASE_URL = "https://pubmed.ncbi.nlm.nih.gov"


async def get_literature(
    client: NCBIClient,
    cache: CacheDB,
    gene_id: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """
    Retrieve PubMed articles linked to a gene via elink + esummary.

    Checks the literature cache first (1-day TTL). On cache miss,
    calls elink to find linked PubMed IDs, then esummary for article details.

    Args:
        client: An initialised NCBIClient instance.
        cache: The CacheDB instance for reading/writing literature cache.
        gene_id: NCBI Gene UID (e.g., "672" for BRCA1).
        max_results: Maximum number of publications to return. Defaults to 5.

    Returns:
        Dict with:
            - "articles": list of formatted article dicts
            - "gene_id": the queried gene ID
            - "total_linked_articles": total PMIDs linked to this gene
    """
    # Step 1: Check cache
    cached_data = cache.get_literature(gene_id)
    if cached_data is not None:
        # Return cached articles, trimmed to max_results
        articles = cached_data[:max_results]
        return {
            "articles": articles,
            "gene_id": gene_id,
            "total_linked_articles": len(cached_data),
            "cached": True,
        }

    # Step 2: Call elink to find linked PubMed IDs
    try:
        pmids = await client.elink(
            dbfrom="gene",
            db="pubmed",
            ids=[gene_id],
            linkname="gene_pubmed",
        )

        if not pmids:
            return {
                "articles": [],
                "gene_id": gene_id,
                "total_linked_articles": 0,
                "cached": False,
                "message": (
                    f"No PubMed articles linked to gene ID '{gene_id}'. "
                    "Some genes have sparse literature coverage."
                ),
            }

        total_linked = len(pmids)

        # Step 3: Take the first max_results PMIDs (returned in relevance order)
        pmids_to_fetch = pmids[:max_results]

        # Step 4: Fetch article summaries from PubMed
        summaries = await client.esummary("pubmed", pmids_to_fetch)

        # Step 5: Format each article
        articles = [_format_article(summary) for summary in summaries]

        # Cache all linked articles (fetch more for cache if available)
        # We cache what we fetched; future calls with higher max_results
        # may need a fresh fetch
        cache.set_literature(gene_id, articles)

        return {
            "articles": articles,
            "gene_id": gene_id,
            "total_linked_articles": total_linked,
            "cached": False,
        }

    except NCBIClientError as e:
        logger.error("NCBI API error during get_literature: %s", str(e))

        # Return stale cache if available
        stale = cache.get_literature(gene_id)
        if stale is not None:
            return {
                "articles": stale[:max_results],
                "gene_id": gene_id,
                "total_linked_articles": len(stale),
                "cached": True,
                "stale_cache": True,
                "message": "Returning stale cached data due to API error.",
            }

        return {
            "articles": [],
            "gene_id": gene_id,
            "total_linked_articles": 0,
            "error": str(e),
            "message": "The NCBI API request failed and no cached data is available. Please try again shortly.",
        }


def _format_article(summary: dict[str, Any]) -> dict[str, Any]:
    """
    Format a raw PubMed esummary response into the tool's output schema.

    Args:
        summary: Raw dict from esummary for a single PubMed article.

    Returns:
        Structured article dict with standardised keys.
    """
    # Format authors: "Smith J, Jones A, et al." for >3 authors
    authors_list = summary.get("authors", [])
    if isinstance(authors_list, list):
        author_names = [a.get("name", "") for a in authors_list if isinstance(a, dict)]
    else:
        author_names = []

    if len(author_names) > 3:
        authors_str = f"{', '.join(author_names[:3])}, et al."
    else:
        authors_str = ", ".join(author_names)

    pmid = summary.get("uid", "")

    return {
        "pmid": pmid,
        "title": summary.get("title", ""),
        "authors": authors_str,
        "journal": summary.get("source", ""),
        "pub_date": summary.get("pubdate", ""),
        "volume": summary.get("volume", ""),
        "pages": summary.get("pages", ""),
        "pubmed_url": f"{PUBMED_BASE_URL}/{pmid}/" if pmid else "",
    }
