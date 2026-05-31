"""
MCP server entry point for mcp-genomics.

Registers all tools, resources, and prompts with the MCP SDK,
manages the NCBIClient lifecycle, and runs via stdio transport.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_genomics.api import NCBIClient
from mcp_genomics.tools.search_genes import search_genes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """
    Manage server-wide resources across the application lifecycle.

    Opens the shared NCBIClient on startup and closes it on shutdown.
    The client is stored in server.state for access by tool handlers.
    """
    async with NCBIClient() as client:
        yield {"ncbi_client": client}


mcp = FastMCP(
    "mcp-genomics",
    description="A genomics intelligence MCP server for biotech & pharma workflows",
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
    client: NCBIClient = mcp.state["ncbi_client"]
    return await search_genes(client, query, organism, max_results)


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")
