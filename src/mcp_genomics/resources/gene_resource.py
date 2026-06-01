"""
MCP resource: gene://ncbi/{gene_id}

Exposes a gene's full profile as a human-readable text resource
that Claude can pull into its context for reference.

Unlike the get_gene_details tool (which returns structured JSON for actions),
this resource returns formatted text for passive context grounding.
"""

from typing import Any

from mcp_genomics.api import NCBIClient
from mcp_genomics.data import CacheDB
from mcp_genomics.tools.gene_details import get_gene_details

NCBI_GENE_BASE_URL = "https://www.ncbi.nlm.nih.gov/gene"


async def read_gene_resource(
    client: NCBIClient,
    cache: CacheDB,
    gene_id: str,
) -> str:
    """
    Produce a human-readable gene profile for context grounding.

    Calls get_gene_details internally (leveraging the cache) and
    formats the result as a readable text block.

    Args:
        client: An initialised NCBIClient instance.
        cache: The CacheDB instance for reading/writing gene cache.
        gene_id: NCBI Gene UID (e.g., "672" for BRCA1).

    Returns:
        Formatted text string of the gene profile.
    """
    details = await get_gene_details(client, cache, gene_id)

    if "error" in details:
        return f"Error: {details.get('error', 'Unknown error')}\n{details.get('message', '')}"

    return _format_gene_text(details, gene_id)


def _format_gene_text(details: dict[str, Any], gene_id: str) -> str:
    """
    Format gene details into a human-readable text block.

    Args:
        details: Gene detail dict from get_gene_details.
        gene_id: NCBI Gene UID.

    Returns:
        Formatted multi-line text string.
    """
    symbol = details.get("symbol", "Unknown")
    full_name = details.get("full_name", "")
    organism = details.get("organism", "")
    chromosome = details.get("chromosome", "")
    map_location = details.get("map_location", "")
    gene_type = details.get("gene_type", "")
    summary = details.get("summary", "No summary available.")
    aliases = details.get("aliases", [])
    diseases = details.get("diseases", [])
    pathways = details.get("pathways", [])
    retrieved_at = details.get("retrieved_at", "")

    # Build header
    header = f"Gene Profile: {symbol} (Gene ID: {gene_id})"
    separator = "=" * len(header)

    # Build chromosome line
    chrom_line = f"Chromosome: {chromosome}"
    if map_location:
        chrom_line += f" ({map_location})"

    # Build sections
    lines = [
        header,
        separator,
        f"Full Name: {full_name}",
        f"Organism: {organism}",
        chrom_line,
        f"Gene Type: {gene_type}",
        "",
        "Summary:",
        summary,
        "",
    ]

    # Aliases
    if aliases:
        lines.append(f"Aliases: {', '.join(aliases)}")
        lines.append("")

    # Diseases (only shown when data is available)
    if diseases:
        lines.append("Associated Diseases:")
        for disease in diseases:
            lines.append(f"  \u2022 {disease}")
        lines.append("")

    # Pathways (only shown when data is available)
    if pathways:
        lines.append("Pathways:")
        for pathway in pathways:
            lines.append(f"  \u2022 {pathway}")
        lines.append("")

    # Footer
    if retrieved_at:
        lines.append(f"Data retrieved: {retrieved_at}")
    lines.append(f"Source: NCBI Gene ({NCBI_GENE_BASE_URL}/{gene_id})")

    return "\n".join(lines)
