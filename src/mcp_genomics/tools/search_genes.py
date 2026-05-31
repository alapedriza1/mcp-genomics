"""
MCP tool: search_genes

Search for genes by keyword, optionally filtered by organism.
Entry point for discovery workflows.

Enterprise use case:
    "Find all genes associated with Alzheimer's disease so I can
    identify candidate therapeutic targets for our pipeline."
"""

import logging
from typing import Any

from mcp_genomics.api import NCBIClient, NCBIClientError

logger = logging.getLogger(__name__)

# Maximum allowed results to avoid hammering the API
MAX_RESULTS_CAP = 50


async def search_genes(
    client: NCBIClient,
    query: str,
    organism: str = "human",
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Search for genes by keyword and return structured summaries.

    Combines esearch + esummary on the NCBI Gene database.

    Args:
        client: An initialised NCBIClient instance.
        query: Search term — gene name, symbol, disease, pathway, or keyword
               (e.g., "BRCA1", "breast cancer", "apoptosis").
        organism: Organism filter (e.g., "human", "mouse"). Defaults to "human".
        max_results: Maximum number of results to return. Clamped to 50.

    Returns:
        Dict with:
            - "results": list of gene summary dicts
            - "total_found": total matching genes in NCBI
            - "query": the search term used
            - "organism": the organism filter applied
            - "clamped": whether max_results was clamped to 50
    """
    # Clamp max_results to avoid excessive API load
    clamped = False
    if max_results > MAX_RESULTS_CAP:
        max_results = MAX_RESULTS_CAP
        clamped = True
        logger.info("max_results clamped to %d", MAX_RESULTS_CAP)

    # Build the Entrez search term with organism filter
    search_term = f"{query} AND {organism}[orgn]"

    try:
        # Step 1: Search for gene IDs
        search_result = await client.esearch("gene", search_term, retmax=max_results)
        id_list = search_result.get("idlist", [])
        total_found = int(search_result.get("count", 0))

        # No results
        if not id_list:
            return {
                "results": [],
                "total_found": 0,
                "query": query,
                "organism": organism,
                "clamped": clamped,
                "message": (
                    f"No genes found matching '{query}' in {organism}. "
                    "Try broadening your search or checking the spelling."
                ),
            }

        # Step 2: Fetch summaries for the returned IDs
        summaries = await client.esummary("gene", id_list)

        # Step 3: Format each result into a structured summary
        results = [_format_gene_summary(summary) for summary in summaries]

        return {
            "results": results,
            "total_found": total_found,
            "query": query,
            "organism": organism,
            "clamped": clamped,
        }

    except NCBIClientError as e:
        logger.error("NCBI API error during search_genes: %s", str(e))
        return {
            "results": [],
            "total_found": 0,
            "query": query,
            "organism": organism,
            "clamped": clamped,
            "error": str(e),
            "message": "The NCBI API request failed. Please try again shortly.",
        }


def _format_gene_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """
    Format a raw NCBI gene summary into the tool's output schema.

    Args:
        summary: Raw dict from esummary for a single gene.

    Returns:
        Structured gene summary with standardised keys.
    """
    description = summary.get("summary", "")
    snippet = description[:200] + "..." if len(description) > 200 else description

    return {
        "gene_id": summary.get("uid", ""),
        "symbol": summary.get("name", ""),
        "name": summary.get("description", ""),
        "organism": summary.get("organism", {}).get("scientificname", ""),
        "chromosome": summary.get("chromosome", ""),
        "map_location": summary.get("maplocation", ""),
        "summary_snippet": snippet,
    }
