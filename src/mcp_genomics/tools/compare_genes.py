"""
MCP tool: compare_genes

Takes 2-5 gene IDs and produces a structured side-by-side comparison.
Reuses get_gene_details (which leverages the cache) for each gene.

Enterprise use case:
    "Compare our top 3 candidate targets (BRCA1, TP53, EGFR) side by side
    so I can brief the portfolio committee on their relative merits."
"""

import logging
from collections import Counter
from typing import Any

from mcp_genomics.api import NCBIClient, NCBIClientError
from mcp_genomics.data import CacheDB
from mcp_genomics.tools.gene_details import get_gene_details

logger = logging.getLogger(__name__)

# Fields to include in the comparison table
COMPARISON_FIELDS = [
    "symbol",
    "full_name",
    "organism",
    "chromosome",
    "map_location",
    "gene_type",
]


async def compare_genes(
    client: NCBIClient,
    cache: CacheDB,
    gene_ids: list[str],
) -> dict[str, Any]:
    """
    Fetch details for multiple genes and produce a structured comparison.

    Calls get_gene_details for each gene (may hit cache), then computes
    overlap analysis for diseases, pathways, and chromosome co-location.

    Args:
        client: An initialised NCBIClient instance.
        cache: The CacheDB instance for reading/writing gene cache.
        gene_ids: List of 2-5 NCBI Gene UIDs to compare.

    Returns:
        Dict with comparison_table, overlap_analysis, and per_gene_details.
    """
    # Validate input
    if len(gene_ids) < 2:
        return {
            "error": "At least 2 gene IDs are required for comparison.",
            "gene_ids": gene_ids,
        }
    if len(gene_ids) > 5:
        return {
            "error": "Maximum 5 gene IDs allowed for comparison.",
            "gene_ids": gene_ids,
        }

    # Fetch details for each gene
    per_gene_details: dict[str, dict[str, Any]] = {}
    failed_ids: list[str] = []

    for gene_id in gene_ids:
        result = await get_gene_details(client, cache, gene_id)
        if "error" in result:
            failed_ids.append(gene_id)
            logger.warning("Failed to fetch gene %s: %s", gene_id, result.get("error"))
        else:
            symbol = result.get("symbol", gene_id)
            per_gene_details[symbol] = result

    # Need at least 2 successful results to compare
    if len(per_gene_details) < 2:
        return {
            "error": "Could not retrieve enough genes for comparison.",
            "failed_ids": failed_ids,
            "message": "At least 2 genes must resolve successfully. Verify the Gene IDs are correct.",
        }

    # Build comparison table
    comparison_table = _build_comparison_table(per_gene_details)

    # Compute overlap analysis
    overlap_analysis = _compute_overlap(per_gene_details)

    result = {
        "genes_compared": len(per_gene_details),
        "comparison_table": comparison_table,
        "overlap_analysis": overlap_analysis,
        "per_gene_details": per_gene_details,
    }

    if failed_ids:
        result["failed_ids"] = failed_ids
        result["message"] = f"Could not retrieve data for gene IDs: {', '.join(failed_ids)}"

    return result


def _build_comparison_table(
    genes: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """
    Build a field-by-field comparison table across all genes.

    Args:
        genes: Dict mapping gene symbol to its full detail dict.

    Returns:
        List of row dicts, each with a "field" key and one key per gene symbol.
    """
    symbols = list(genes.keys())
    table: list[dict[str, str]] = []

    for field in COMPARISON_FIELDS:
        row: dict[str, str] = {"field": field}
        for symbol in symbols:
            row[symbol] = str(genes[symbol].get(field, ""))
        table.append(row)

    return table


def _compute_overlap(genes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Compute overlap analysis: shared diseases, shared pathways,
    and chromosome co-location.

    Args:
        genes: Dict mapping gene symbol to its full detail dict.

    Returns:
        Dict with shared_diseases, shared_pathways, and
        chromosome_co_location fields.
    """
    symbols = list(genes.keys())

    # Shared diseases (appearing in 2+ genes)
    all_diseases: list[str] = []
    for details in genes.values():
        all_diseases.extend(details.get("diseases", []))
    disease_counts = Counter(all_diseases)
    shared_diseases = [d for d, count in disease_counts.items() if count >= 2]

    # Shared pathways (appearing in 2+ genes)
    all_pathways: list[str] = []
    for details in genes.values():
        all_pathways.extend(details.get("pathways", []))
    pathway_counts = Counter(all_pathways)
    shared_pathways = [p for p, count in pathway_counts.items() if count >= 2]

    # Chromosome co-location
    chrom_map: dict[str, list[str]] = {}
    for symbol, details in genes.items():
        chrom = details.get("chromosome", "")
        if chrom:
            chrom_map.setdefault(chrom, []).append(symbol)

    co_located = {
        chrom: genes_on_chrom
        for chrom, genes_on_chrom in chrom_map.items()
        if len(genes_on_chrom) >= 2
    }
    same_chromosome = len(co_located) > 0

    if co_located:
        details_parts = [
            f"{', '.join(genes_on_chrom)} are on chromosome {chrom}"
            for chrom, genes_on_chrom in co_located.items()
        ]
        details_str = "; ".join(details_parts)
    else:
        details_str = "All genes are on different chromosomes"

    return {
        "shared_diseases": shared_diseases,
        "shared_pathways": shared_pathways,
        "chromosome_co_location": {
            "same_chromosome": same_chromosome,
            "details": details_str,
        },
    }
