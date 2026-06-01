"""
MCP server entry point for mcp-genomics.

Registers all tools, resources, and prompts with the MCP SDK,
manages the NCBIClient lifecycle, and runs via stdio transport.

Configuration via environment variables:
    NCBI_EMAIL   — Email address sent with API requests (courtesy, not enforced).
    NCBI_API_KEY — Optional API key for 10 req/s rate limit (default is 3 req/s).
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_genomics.api import NCBIClient
from mcp_genomics.data import CacheDB
from mcp_genomics.tools.search_genes import search_genes
from mcp_genomics.tools.gene_details import get_gene_details

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module-level references, set during lifespan
_ncbi_client: NCBIClient | None = None
_cache: CacheDB | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    """
    Manage server-wide resources across the application lifecycle.

    Opens the shared NCBIClient and CacheDB on startup,
    closes them on shutdown.
    """
    global _ncbi_client, _cache

    email = os.environ.get("NCBI_EMAIL")
    api_key = os.environ.get("NCBI_API_KEY")

    if not email:
        logger.warning(
            "NCBI_EMAIL not set. NCBI recommends providing an email for API access."
        )

    _cache = CacheDB()
    _cache.purge_expired()

    async with NCBIClient(email=email, api_key=api_key) as client:
        _ncbi_client = client
        yield
    _ncbi_client = None
    _cache.close()
    _cache = None


mcp = FastMCP(
    "mcp-genomics",
    instructions="A genomics intelligence MCP server for biotech & pharma workflows",
    lifespan=lifespan,
)


# ─── Tools ────────────────────────────────────────────────────────────────────


@mcp.tool()
async def search_genes_tool(
    query: str,
    organism: str = "human",
    max_results: int = 10,
) -> dict[str, Any]:
    """
    Search for genes by keyword, optionally filtered by organism.

    Use this to find genes associated with a disease, pathway, or function.

    Args:
        query: Search term — gene name, symbol, disease, pathway, or keyword
               (e.g., "BRCA1", "breast cancer", "apoptosis").
        organism: Organism filter (e.g., "human", "mouse"). Defaults to "human".
        max_results: Maximum number of results to return (max 50). Defaults to 10.

    Returns:
        A list of matching genes with ID, symbol, name, organism,
        chromosome, map location, and a summary snippet.
    """
    if _ncbi_client is None:
        return {"error": "NCBI client not initialised", "results": []}
    return await search_genes(_ncbi_client, query, organism, max_results)


@mcp.tool()
async def get_gene_details_tool(
    gene_id: str,
) -> dict[str, Any]:
    """
    Get a comprehensive profile of a specific gene by its NCBI Gene ID.

    Use this after search_genes to get the full details on a specific gene,
    including function summary, aliases, chromosome location, and gene type.

    Args:
        gene_id: NCBI Gene ID (e.g., "672" for BRCA1). Obtain this from search_genes.

    Returns:
        A complete gene profile with symbol, full name, organism, chromosome,
        map location, gene type, full summary, aliases, diseases, and pathways.
    """
    if _ncbi_client is None or _cache is None:
        return {"error": "Server not initialised", "gene_id": gene_id}
    return await get_gene_details(_ncbi_client, _cache, gene_id)


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")
