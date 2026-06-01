"""
MCP tool: get_gene_details

Get a comprehensive profile of a specific gene by its NCBI Gene ID.
The "deep dive" tool.

Enterprise use case:
    "Pull the full profile on TP53 — function, pathways,
    disease links — for my target assessment report."
"""

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

from mcp_genomics.api import NCBIClient, NCBIClientError
from mcp_genomics.data import CacheDB

logger = logging.getLogger(__name__)


async def get_gene_details(
    client: NCBIClient,
    cache: CacheDB,
    gene_id: str,
) -> dict[str, Any]:
    """
    Fetch a comprehensive profile for a single gene.

    Checks the SQLite cache first (7-day TTL). On cache miss,
    calls esummary for core fields and efetch XML for diseases
    and pathways, then caches the combined result.

    Args:
        client: An initialised NCBIClient instance.
        cache: The CacheDB instance for reading/writing gene cache.
        gene_id: NCBI Gene UID (e.g., "672" for BRCA1).

    Returns:
        Dict with full gene profile including symbol, name, organism,
        chromosome, map location, gene type, summary, aliases, diseases,
        pathways, and cache metadata.
    """
    # Step 1: Check cache
    cached_data = cache.get_gene(gene_id)
    if cached_data is not None:
        cached_data["cached"] = True
        return cached_data

    # Step 2: Fetch from NCBI API
    try:
        summaries = await client.esummary("gene", [gene_id])

        if not summaries:
            return {
                "error": f"Gene ID '{gene_id}' not found in NCBI Gene database.",
                "gene_id": gene_id,
                "message": "Verify the Gene ID is correct. Use search_genes to find valid IDs.",
            }

        raw = summaries[0]
        result = _format_gene_details(raw)

        # Step 3: Enrich with efetch XML (diseases, pathways)
        try:
            xml_text = await client.efetch_xml("gene", gene_id)
            diseases, pathways = _parse_gene_xml(xml_text)
            result["diseases"] = diseases
            result["pathways"] = pathways
        except Exception as e:
            logger.warning("XML enrichment failed for gene %s: %s", gene_id, str(e))
            # Non-fatal — we still have the esummary data

        # Step 4: Cache the result
        cache.set_gene(gene_id, result)

        result["cached"] = False
        return result

    except NCBIClientError as e:
        logger.error("NCBI API error during get_gene_details: %s", str(e))

        # Return stale cache if available
        stale = cache.get_gene(gene_id)
        if stale is not None:
            stale["cached"] = True
            stale["stale_cache"] = True
            stale["message"] = "Returning stale cached data due to API error."
            return stale

        return {
            "error": str(e),
            "gene_id": gene_id,
            "message": "The NCBI API request failed and no cached data is available. Please try again shortly.",
        }


def _format_gene_details(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Format a raw NCBI gene esummary response into the tool's output schema.

    Args:
        raw: Raw dict from esummary for a single gene.

    Returns:
        Structured gene detail dict with standardised keys.
    """
    # Extract organism info
    organism = raw.get("organism", {})
    organism_name = organism.get("scientificname", "") if isinstance(organism, dict) else ""

    # Extract aliases from otheraliases field (comma-separated string)
    aliases_str = raw.get("otheraliases", "")
    aliases = [a.strip() for a in aliases_str.split(",") if a.strip()] if aliases_str else []

    return {
        "gene_id": raw.get("uid", ""),
        "symbol": raw.get("name", ""),
        "full_name": raw.get("description", ""),
        "organism": organism_name,
        "chromosome": raw.get("chromosome", ""),
        "map_location": raw.get("maplocation", ""),
        "gene_type": raw.get("geneticsource", ""),
        "summary": raw.get("summary", ""),
        "aliases": aliases,
        "diseases": [],
        "pathways": [],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def _parse_gene_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """
    Parse diseases and pathways from an NCBI efetch gene XML response.

    Diseases are found in Gene-commentary elements with heading "Diseases"
    under Entrezgene_comments. Pathways are found under headings containing
    "Pathways" or within KEGG/Reactome pathway annotations.

    Args:
        xml_text: Raw XML string from efetch.

    Returns:
        Tuple of (diseases list, pathways list).
    """
    diseases: list[str] = []
    pathways: list[str] = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse gene XML")
        return diseases, pathways

    # The XML structure has nested Gene-commentary elements.
    # We search for all Gene-commentary elements and inspect their headings.
    for commentary in root.iter("Gene-commentary"):
        heading_elem = commentary.find("Gene-commentary_heading")
        if heading_elem is None or heading_elem.text is None:
            continue

        heading = heading_elem.text.strip()

        # Extract diseases
        if heading.lower() == "diseases":
            diseases = _extract_commentary_labels(commentary)

        # Extract pathways (various headings)
        if "pathway" in heading.lower():
            pathways.extend(_extract_commentary_labels(commentary))

    # Deduplicate while preserving order
    pathways = list(dict.fromkeys(pathways))

    return diseases, pathways


def _extract_commentary_labels(commentary: ET.Element) -> list[str]:
    """
    Extract text labels from nested Gene-commentary elements.

    Looks for Gene-commentary_text or Gene-commentary_heading in
    child commentaries under the given parent commentary.

    Args:
        commentary: A Gene-commentary XML element.

    Returns:
        List of label strings found.
    """
    labels: list[str] = []

    # Look in sub-commentaries
    for sub in commentary.iter("Gene-commentary"):
        # Skip the parent itself
        if sub is commentary:
            continue

        # Try text first (more descriptive)
        text_elem = sub.find("Gene-commentary_text")
        if text_elem is not None and text_elem.text:
            labels.append(text_elem.text.strip())
            continue

        # Fall back to heading
        heading_elem = sub.find("Gene-commentary_heading")
        if heading_elem is not None and heading_elem.text:
            labels.append(heading_elem.text.strip())

    return labels
