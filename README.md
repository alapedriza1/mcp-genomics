# mcp-genomics 🧬

An MCP server that gives Claude access to genomics intelligence —
built for biotech & pharma enterprise workflows.

---

## The Scenario

You're a Field Discovery Engineer at a biotech customer. Their drug discovery analysts spend hours manually querying NCBI databases, cross-referencing genes, and compiling target assessment reports. You build an MCP server that puts real-time genomics intelligence directly in Claude's hands — turning multi-hour research workflows into conversational interactions.

## What It Does

- **Search genes** across NCBI databases by keyword, disease, pathway, or function
- **Pull detailed gene profiles** with disease associations and pathway data
- **Compare candidate therapeutic targets** side by side with overlap analysis
- **Surface recent PubMed evidence** linked to any gene — citable, with URLs
- **Pre-built prompt templates** for target assessment and pipeline comparison workflows
- **Local glossary** of genomics terminology with enterprise context for non-specialist audiences

## Demo

> "Search for genes associated with Alzheimer's disease"

<!-- Paste screenshot here: gene search results in Claude Desktop -->

> "Do a target assessment on BRCA1 in the context of breast cancer"

<!-- Paste screenshot here: full target assessment workflow output -->

> "Compare TP53, BRCA1, and EGFR for our oncology pipeline"

<!-- Paste screenshot here: pipeline comparison with recommendation matrix -->

> **Tip:** To add screenshots, edit this README on github.com and paste/drag images directly into the editor — GitHub hosts them automatically.

## Architecture

```
┌──────────────────────────────────────────────────┐
│               Claude Desktop App                  │
│          (or any MCP-compatible client)           │
└──────────────────┬───────────────────────────────┘
                   │ MCP Protocol (stdio transport)
                   │
┌──────────────────▼───────────────────────────────┐
│              mcp-genomics server                  │
│            (Python, runs locally)                 │
│                                                   │
│  ┌───────────────────┐  ┌──────────────────────┐ │
│  │     4 TOOLS        │  │    2 RESOURCES       │ │
│  │                    │  │                      │ │
│  │ • search_genes     │  │ • gene://ncbi/{id}   │ │
│  │ • get_gene_details │  │ • glossary://genomics │ │
│  │ • compare_genes    │  │   /{term}            │ │
│  │ • get_literature   │  │                      │ │
│  └────────┬───────────┘  └──────────┬───────────┘ │
│           │                         │              │
│  ┌────────▼─────────────────────────▼───────────┐ │
│  │           DATA / INTEGRATION LAYER            │ │
│  │                                               │ │
│  │  • ncbi_client.py  (NCBI Entrez API wrapper)  │ │
│  │  • cache.py        (SQLite caching layer)     │ │
│  │  • glossary/       (local YAML files)         │ │
│  └───────────────────────────────────────────────┘ │
│                                                   │
│  ┌───────────────────┐                            │
│  │    2 PROMPTS       │                            │
│  │                    │                            │
│  │ • target_          │                            │
│  │   assessment       │                            │
│  │ • pipeline_        │                            │
│  │   comparison       │                            │
│  └───────────────────┘                            │
└───────────────────────────────────────────────────┘
                   │
                   ▼ (HTTP calls from ncbi_client.py)
┌───────────────────────────────────────────────────┐
│           NCBI Entrez API (external)              │
│         https://eutils.ncbi.nlm.nih.gov           │
│                                                   │
│  • esearch  — search genes by keyword             │
│  • esummary — get summary records                 │
│  • efetch   — get full gene records (XML)         │
│  • elink    — find linked PubMed articles         │
│                                                   │
│  Free, no auth required (just an email header).   │
└───────────────────────────────────────────────────┘
```

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/your-username/mcp-genomics.git
cd mcp-genomics
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
```

### 2. Configure Claude Desktop

Add to your Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "mcp-genomics": {
      "command": "C:/path/to/your/.venv/Scripts/python.exe",
      "args": ["-m", "mcp_genomics"],
      "env": {
        "NCBI_EMAIL": "your.email@example.com"
      }
    }
  }
}
```

> **Note:** Use the full path to your venv's `python.exe` — Claude Desktop doesn't inherit your shell PATH.

### 3. Restart Claude Desktop

The server appears in the MCP tools menu (hammer icon).

## Tools Reference

| Tool | Description | Example Input |
| --- | --- | --- |
| `search_genes` | Search NCBI Gene by keyword, disease, or pathway | `query="BRCA1", organism="human"` |
| `get_gene_details` | Full gene profile with diseases and pathways | `gene_id="672"` |
| `compare_genes` | Side-by-side comparison of 2–5 genes | `gene_ids=["672", "7157", "1956"]` |
| `get_literature` | Recent PubMed publications linked to a gene | `gene_id="672", max_results=5` |

## Resources Reference

| URI Pattern | Description |
| --- | --- |
| `gene://ncbi/{gene_id}` | Human-readable gene profile for context grounding |
| `glossary://genomics/{term}` | Plain-English definition with enterprise context |

The glossary includes 19 terms covering key concepts that appear in tool outputs — from `kinase` and `oncogene` to `druggable_target` and `biomarker`.

## Prompt Templates

| Prompt | Purpose | Arguments |
| --- | --- | --- |
| `target_assessment` | Structured therapeutic target report for portfolio review | `gene_name` (required), `disease_context` (optional) |
| `pipeline_comparison` | Side-by-side comparison report for pipeline prioritisation | `gene_names` (required, comma-separated), `disease_context` (optional) |

Prompts guide Claude through multi-step workflows: search → profile → literature → synthesise into a structured report. The user doesn't need to know prompt names — they just describe what they want.

## Design Decisions

### Deterministic tools for computation

Gene comparisons, overlap analysis, and data formatting are done in Python — not delegated to Claude. This ensures consistent, reproducible outputs even as the LLM changes.

### SQLite caching

NCBI allows 3 requests/second (10 with an API key). Within a single `target_assessment` workflow, Claude may call `get_gene_details` multiple times for the same gene. The 7-day gene cache and 1-day literature cache eliminate redundant API calls, reduce latency, and provide offline resilience for recently-accessed data.

### Enterprise framing

A genomics MCP server could serve academic researchers, but framing it for biotech/pharma enterprise workflows (target assessment, pipeline comparison, portfolio review) demonstrates how MCP enables domain-specific AI tooling at the organisational level.

### Resource + tool separation

Tools perform actions and return structured data. Resources provide context that Claude can pull into its window passively. The `gene://ncbi/{id}` resource gives Claude a gene profile *without* using a tool call — useful when Claude needs background context to answer a follow-up question.

## Testing

```bash
pip install -e ".[dev]"
pytest
```

Tests use saved NCBI API response fixtures (`tests/fixtures/`) — they run without network access, are fast and deterministic.

**Coverage:**
- `test_search_genes.py` — search results, no-results handling, max_results clamping
- `test_gene_details.py` — full profile, caching, invalid IDs, XML enrichment failure
- `test_compare_genes.py` — comparison table, shared chromosome detection, input validation
- `test_literature.py` — article formatting, author truncation, caching
- `test_cache.py` — set/get, expiry, overwrite, purge, clear

## What I'd Build Next

- **Additional data sources** — UniProt for protein structure/function, Ensembl for variant data, ClinVar for clinical significance
- **SSE transport** — enable remote deployment behind a corporate proxy, serve multiple analysts from one instance
- **Authentication layer** — API key management, rate limiting per user, audit logging for enterprise compliance
- **Usage analytics** — track which genes/diseases are most queried, surface trending targets across the organisation
- **Prompt library expansion** — competitive landscape analysis, safety pharmacology review, patent landscape summary

## About

Built by Alberto Lapedriza — AI engineer with a background in computational biology. This project demonstrates MCP server development for the biotech/pharma vertical: connecting LLMs to real scientific databases with production engineering practices (caching, rate limiting, error handling, test coverage).
