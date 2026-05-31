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
from mcp_genomics.tools.search_genes import search_genes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module-level client reference, set during lifespan
_ncbi_client: NCBIClient | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    """
    Manage server-wide resources across the application lifecycle.

    Opens the shared NCBIClient on startup and closes it on shutdown.
    """
    global _ncbi_client

    email = os.environ.get("NCBI_EMAIL")
    api_key = os.environ.get("NCBI_API_KEY")

    if not email:
        logger.warning(
            "NCBI_EMAIL not set. NCBI recommends providing an email for API access."
        )

    async with NCBIClient(email=email, api_key=api_key) as client:
        _ncbi_client = client
        yield
    _ncbi_client = None


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


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")
