"""
MCP resource: glossary://genomics/{term}

A local glossary of genomics and drug-discovery terminology, so Claude
can explain results clearly to non-expert enterprise users.

Implementation: reads from data/glossary/genomics.yaml (no API call needed).
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Locate the glossary YAML relative to the project root
# The file lives at: <project_root>/data/glossary/genomics.yaml
# This module lives at: <project_root>/src/mcp_genomics/resources/glossary_resource.py
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_GLOSSARY_PATH = _PROJECT_ROOT / "data" / "glossary" / "genomics.yaml"

# Module-level cache of the parsed glossary
_glossary: dict[str, dict[str, str]] | None = None


def _load_glossary() -> dict[str, dict[str, str]]:
    """
    Load and cache the glossary YAML file.

    Returns:
        Dict mapping term keys (e.g., "gene_expression") to their
        definition dicts with 'term', 'definition', 'enterprise_context'.

    Raises:
        FileNotFoundError: If the glossary YAML file is missing.
    """
    global _glossary
    if _glossary is not None:
        return _glossary

    if not _GLOSSARY_PATH.exists():
        raise FileNotFoundError(
            f"Glossary file not found at {_GLOSSARY_PATH}. "
            "Ensure data/glossary/genomics.yaml exists in the project root."
        )

    with open(_GLOSSARY_PATH, "r", encoding="utf-8") as f:
        _glossary = yaml.safe_load(f)

    logger.info("Loaded glossary with %d terms", len(_glossary))
    return _glossary


def get_available_terms() -> list[str]:
    """
    Return a list of all available glossary term keys.

    Returns:
        List of term keys (e.g., ["gene_expression", "protein_coding", ...])
    """
    glossary = _load_glossary()
    return list(glossary.keys())


def read_glossary_term(term: str) -> str:
    """
    Look up a glossary term and return a human-readable text block.

    The term key is normalised (lowercased, spaces replaced with underscores)
    before lookup.

    Args:
        term: Glossary term key (e.g., "gene_expression", "kinase").
              Also accepts "Gene Expression" or "gene expression" forms.

    Returns:
        Formatted text string with the term definition and enterprise context,
        or an error message if the term is not found.
    """
    glossary = _load_glossary()

    # Normalise the lookup key
    key = term.lower().replace(" ", "_").replace("-", "_")

    entry = glossary.get(key)
    if entry is None:
        available = ", ".join(sorted(glossary.keys()))
        return (
            f"Term '{term}' not found in the genomics glossary.\n\n"
            f"Available terms: {available}"
        )

    return _format_glossary_entry(entry)


def _format_glossary_entry(entry: dict[str, str]) -> str:
    """
    Format a glossary entry into a human-readable text block.

    Args:
        entry: Dict with 'term', 'definition', 'enterprise_context'.

    Returns:
        Formatted multi-line text string.
    """
    term_name = entry.get("term", "Unknown")
    definition = entry.get("definition", "")
    enterprise_context = entry.get("enterprise_context", "")

    lines = [
        f"Glossary: {term_name}",
        "─" * (len(f"Glossary: {term_name}")),
        "",
        f"Definition: {definition}",
        "",
    ]

    if enterprise_context:
        lines.append(f"Enterprise Context: {enterprise_context}")

    return "\n".join(lines)
