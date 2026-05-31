# mcp-genomics — Full Scope & Specification Document

## 1. Project Overview

### 1.1 What We're Building

An MCP (Model Context Protocol) server called `mcp-genomics` that gives Claude the ability to act as a genomics research assistant for biotech and pharma enterprise teams. The server exposes structured tools for querying public biological databases, MCP resources for data grounding, and MCP prompt templates for multi-step enterprise workflows.

### 1.2 Enterprise Scenario

You are an Anthropic Forward Deployed Engineer embedded with a mid-size biotech customer. Their drug discovery analysts spend hours manually researching therapeutic gene targets across multiple databases (NCBI, PubMed) before portfolio review meetings. You build them an MCP server that lets Claude pull structured data from public biological databases, run comparisons, and produce enterprise-ready briefings — grounded in real data, not hallucinated.

### 1.3 What This Project Demonstrates

| Skill | How it's demonstrated |
|---|---|
| JD mapping | MCP server development — the entire project |
| Tool design for agentic workflows | 4 tools with clear input/output contracts: "sub-agents, and agent skills that will be used in production workflows" |
| Enterprise framing | Prompts, README, and demo all oriented around business user personas: "customer-facing skills to understand customer workflows" |
| Codifying repeatable patterns | Documented architecture, reusable prompt templates: "Identify and codify repeatable deployment patterns" |
| Evaluation | Automated test suite with known-input/expected-output checks: "evaluation frameworks" |
| Cross-vertical domain fluency | Genomics domain, activated by PhD + MSc background: "healthcare/life sciences...is a plus" |
| Communication | README write-up, architecture diagrams, demo: "convey technical concepts to diverse stakeholders" |

### 1.4 Constraints

| Constraint | Detail |
|---|---|
| Runs entirely locally | No cloud deployment. MCP stdio transport to Claude Desktop. |
| No paid APIs | All external data sources are free public APIs (NCBI Entrez). |
| No GPU required | No ML inference — tools are API calls + Python data manipulation. |
| Python only | Aligns with your primary language. |
| Build time | ~10–15 hours across 1.5–2 weekends. |

---

## 2. Architecture

### 2.1 System Diagram

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
│  • efetch   — get full gene records               │
│  • elink    — find linked PubMed articles         │
│                                                   │
│  Free, no auth required (just an email header).   │
└───────────────────────────────────────────────────┘
```

### 2.2 Transport

`stdio` — the MCP server communicates with Claude Desktop via standard input/output. No HTTP server, no ports, no networking configuration. Claude Desktop spawns the process and talks to it directly.

### 2.3 Dependencies

| Package | Purpose | Notes |
|---|---|---|
| `mcp` | Anthropic's official MCP Python SDK | Core framework. Handles protocol, tool registration, resource serving. |
| `httpx` | Async HTTP client | For calling NCBI Entrez APIs. Preferred over `requests` because the MCP SDK is async-native. |
| `sqlite3` | Caching layer | Part of Python stdlib — no install needed. |
| `pyyaml` | Parse glossary files | For the local YAML glossary resource. |
| `pytest` | Testing | For the evaluation / test suite. |

No other dependencies. No LangChain, no LangGraph, no heavy frameworks.

---

## 3. NCBI Entrez API — Reference

This section gives you everything you need to know to build the API integration layer. All tools ultimately call these endpoints.

### 3.1 Base URL

```
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
```

### 3.2 Required Parameters (All Calls)

| Param | Value | Notes |
|---|---|---|
| `retmode` | `json` | Return JSON (default is XML for some endpoints). |
| `email` | Your email address | NCBI asks for this as a courtesy. Not enforced, but good practice. |
| `tool` | `mcp-genomics` | Identifies your application. Optional but polite. |

### 3.3 Rate Limits

- Without API key: 3 requests/second
- With API key (free): 10 requests/second

For this project, 3/sec is more than enough. No API key needed.

### 3.4 Endpoints You'll Use

#### `esearch` — Search for genes by keyword

```
GET esearch.fcgi?db=gene&term={query}&retmode=json&retmax={max_results}
```

Returns: A list of Gene IDs matching the search term.

**Example:**

```
GET esearch.fcgi?db=gene&term=BRCA1+AND+human[orgn]&retmode=json&retmax=5
```

**Response structure:**

```json
{
  "esearchresult": {
    "count": "1",
    "idlist": ["672"],
    "querytranslation": "BRCA1 AND human[orgn]"
  }
}
```

#### `esummary` — Get summary info for gene IDs

```
GET esummary.fcgi?db=gene&id={comma_separated_ids}&retmode=json
```

Returns: Summary records with name, description, organism, chromosome, map location.

**Response structure (per gene):**

```json
{
  "result": {
    "672": {
      "uid": "672",
      "name": "BRCA1",
      "description": "BRCA1 DNA repair associated",
      "organism": {"scientificname": "Homo sapiens", "commonname": "human"},
      "chromosome": "17",
      "maplocation": "17q21.31",
      "summary": "This gene encodes a nuclear phosphoprotein..."
    }
  }
}
```

#### `efetch` — Get full gene record

```
GET efetch.fcgi?db=gene&id={gene_id}&retmode=xml
```

> **Note:** The gene database `efetch` returns XML only (no JSON option). You'll need to parse XML here. Use Python's `xml.etree.ElementTree` (stdlib).

**Key fields to extract from the XML:**

- Gene official symbol and full name
- Summary / function description
- Organism
- Chromosome and map location
- Gene type (`protein-coding`, `ncRNA`, etc.)
- Associated pathways (if present in the `Entrezgene_comments` section)
- Disease associations (from `Entrezgene_comments` → `Gene-commentary` with heading `"Diseases"`)
- Aliases / other names

> **Alternative approach (simpler):** Use `esummary` for most fields (returns JSON) and only use `efetch` if you want the full richness. For MVP, `esummary` may be sufficient — see Section 6 on phasing.

#### `elink` — Find linked PubMed articles for a gene

```
GET elink.fcgi?dbfrom=gene&db=pubmed&id={gene_id}&retmode=json&linkname=gene_pubmed
```

Returns: A list of PubMed IDs (PMIDs) linked to the gene.

**Response structure:**

```json
{
  "linksets": [{
    "ids": [{"value": "672"}],
    "linksetdbs": [{
      "linkname": "gene_pubmed",
      "links": ["39145678", "39098234", "39001456"]
    }]
  }]
}
```

Then fetch article summaries with:

```
GET esummary.fcgi?db=pubmed&id={comma_separated_pmids}&retmode=json&retmax=10
```

**PubMed summary fields:**

```json
{
  "result": {
    "39145678": {
      "uid": "39145678",
      "pubdate": "2024 Jul",
      "source": "Nature",
      "title": "New insights into BRCA1...",
      "authors": [{"name": "Smith J"}, {"name": "Jones A"}],
      "lastauthor": "Jones A",
      "volume": "631",
      "pages": "123-130"
    }
  }
}
```

---

## 4. MCP Components — Detailed Specifications

### 4.1 Tool: `search_genes`

**Purpose:** Search for genes by keyword, optionally filtered by organism. Entry point for discovery workflows.

**Enterprise use case:** *"Find all genes associated with Alzheimer's disease so I can identify candidate therapeutic targets for our pipeline."*

#### Input Schema

```json
{
  "query": {
    "type": "string",
    "description": "Search term: gene name, symbol, disease, pathway, or keyword (e.g., 'BRCA1', 'breast cancer', 'apoptosis')",
    "required": true
  },
  "organism": {
    "type": "string",
    "description": "Organism filter (e.g., 'human', 'mouse'). Defaults to 'human'.",
    "required": false,
    "default": "human"
  },
  "max_results": {
    "type": "integer",
    "description": "Maximum number of results to return. Defaults to 10.",
    "required": false,
    "default": 10
  }
}
```

#### Implementation Logic

1. Call `esearch` with `db=gene`, `term={query} AND {organism}[orgn]`, `retmax={max_results}`
2. Take the returned Gene IDs
3. Call `esummary` with `db=gene`, `id={comma_separated_ids}`
4. Format each result into a structured summary

#### Output Format (per gene)

```json
{
  "gene_id": "672",
  "symbol": "BRCA1",
  "name": "BRCA1 DNA repair associated",
  "organism": "Homo sapiens",
  "chromosome": "17",
  "map_location": "17q21.31",
  "summary_snippet": "This gene encodes a nuclear phosphoprotein... [first 200 chars]"
}
```

Return: A list of these objects, plus a `total_found` count from the `esearch` response.

#### Error Handling

- If `esearch` returns 0 results: return a clear message saying no genes matched, suggest broadening the query
- If the API call fails (network error, timeout): return a structured error with the HTTP status and a retry suggestion
- If `max_results > 50`: clamp to 50 and note in the response (avoid hammering the API)

---

### 4.2 Tool: `get_gene_details`

**Purpose:** Get a comprehensive profile of a specific gene by its NCBI Gene ID. The "deep dive" tool.

**Enterprise use case:** *"Pull the full profile on TP53 — function, pathways, disease links — for my target assessment report."*

#### Input Schema

```json
{
  "gene_id": {
    "type": "string",
    "description": "NCBI Gene ID (e.g., '672' for BRCA1). Obtain this from search_genes.",
    "required": true
  }
}
```

#### Implementation Logic

1. Check SQLite cache first — if we have a record for this `gene_id` that's less than 7 days old, return it
2. If not cached: call `esummary` with `db=gene`, `id={gene_id}` for the core fields
3. Enrichment *(stretch — see phasing in Section 6)*: Optionally call `efetch` for the full XML record and parse out pathways and disease associations
4. Cache the result in SQLite with a timestamp
5. Format and return

#### Output Format

```json
{
  "gene_id": "672",
  "symbol": "BRCA1",
  "full_name": "BRCA1 DNA repair associated",
  "organism": "Homo sapiens",
  "chromosome": "17",
  "map_location": "17q21.31",
  "gene_type": "protein-coding",
  "summary": "This gene encodes a nuclear phosphoprotein that plays a role in maintaining genomic stability...",
  "aliases": ["IRIS", "PSCP", "BRCAI", "BRCC1", "FANCS", "RNF53"],
  "diseases": ["Breast-ovarian cancer, familial 1", "Fanconi anemia, complementation group S"],
  "pathways": ["DNA double-strand break repair", "Homologous recombination"],
  "cached": false,
  "retrieved_at": "2025-01-15T10:30:00Z"
}
```

> **Note on `diseases` and `pathways`:** These fields come from the XML `efetch` response. If you implement only the `esummary` approach for MVP, these arrays will be empty — that's fine, you can note *"pathway and disease data available via full record"* and add it in the enrichment phase.

#### Error Handling

- If `gene_id` doesn't exist: return a clear "Gene ID not found" message
- If API fails: return cached data if available (even if stale), with a `stale_cache: true` flag

---

### 4.3 Tool: `compare_genes`

**Purpose:** Takes 2–3 gene IDs and produces a structured side-by-side comparison. Pure Python logic — no additional API calls beyond what `get_gene_details` already provides.

**Enterprise use case:** *"Compare our top 3 candidate targets (BRCA1, TP53, EGFR) side by side so I can brief the portfolio committee on their relative merits."*

#### Input Schema

```json
{
  "gene_ids": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of 2-3 NCBI Gene IDs to compare",
    "required": true,
    "minItems": 2,
    "maxItems": 5
  }
}
```

#### Implementation Logic

1. Call `get_gene_details` for each gene ID (these may hit cache)
2. Align the results into a comparison structure
3. Compute overlap fields:
   - `shared_diseases`: diseases that appear in 2+ genes' disease lists
   - `shared_pathways`: pathways that appear in 2+ genes' pathway lists
   - `same_chromosome`: boolean — are any on the same chromosome?
4. Format into a comparison table + overlap summary

#### Output Format

```json
{
  "genes_compared": 3,
  "comparison_table": [
    {
      "field": "symbol",
      "BRCA1": "BRCA1",
      "TP53": "TP53",
      "EGFR": "EGFR"
    },
    {
      "field": "chromosome",
      "BRCA1": "17",
      "TP53": "17",
      "EGFR": "7"
    },
    {
      "field": "gene_type",
      "BRCA1": "protein-coding",
      "TP53": "protein-coding",
      "EGFR": "protein-coding"
    }
  ],
  "overlap_analysis": {
    "shared_diseases": ["Li-Fraumeni syndrome"],
    "shared_pathways": ["DNA repair", "Apoptosis"],
    "chromosome_co_location": {
      "same_chromosome": true,
      "details": "BRCA1 and TP53 are both on chromosome 17"
    }
  },
  "per_gene_details": {
    "BRCA1": { "...full get_gene_details output..." },
    "TP53": { "...full get_gene_details output..." },
    "EGFR": { "...full get_gene_details output..." }
  }
}
```

#### Error Handling

- If fewer than 2 valid gene IDs: return error asking for at least 2
- If one gene ID fails to resolve: compare the ones that succeeded, note which failed

---

### 4.4 Tool: `get_literature`

**Purpose:** Retrieve recent PubMed publications linked to a gene. Grounds Claude's analysis in real, citable evidence.

**Enterprise use case:** *"What's been published on KRAS recently? I need to know if there's new evidence before our R&D pipeline review."*

#### Input Schema

```json
{
  "gene_id": {
    "type": "string",
    "description": "NCBI Gene ID to find literature for",
    "required": true
  },
  "max_results": {
    "type": "integer",
    "description": "Maximum number of publications to return. Defaults to 5.",
    "required": false,
    "default": 5
  }
}
```

#### Implementation Logic

1. Call `elink` with `dbfrom=gene`, `db=pubmed`, `id={gene_id}`, `linkname=gene_pubmed`
2. Extract the list of PMIDs from the response
3. Take the first `max_results` PMIDs (the API returns them in relevance order)
4. Call `esummary` with `db=pubmed`, `id={comma_separated_pmids}`
5. Format each article into a structured summary

#### Output Format (per article)

```json
{
  "pmid": "39145678",
  "title": "New insights into BRCA1-mediated DNA repair mechanisms",
  "authors": "Smith J, Jones A, Chen L, et al.",
  "journal": "Nature",
  "pub_date": "2024 Jul",
  "volume": "631",
  "pages": "123-130",
  "pubmed_url": "https://pubmed.ncbi.nlm.nih.gov/39145678/"
}
```

Return: A list of article objects, plus the `gene_symbol` and `total_linked_articles` count.

#### Error Handling

- If `elink` returns no linked articles: return a clear message (some genes have sparse literature)
- If PubMed `esummary` fails for some PMIDs: return the ones that succeeded

---

## 5. MCP Resources — Detailed Specifications

### 5.1 Resource: `gene://ncbi/{gene_id}`

**Purpose:** Exposes a gene's full profile as an MCP resource that Claude can read into its context. This is different from the `get_gene_details` tool — a resource is pulled into context for reference, while a tool is called to take an action.

**URI Template:** `gene://ncbi/{gene_id}`

**Implementation:** When Claude reads this resource, the server calls `get_gene_details` internally (leveraging the cache) and returns the full profile as formatted text.

**Return Format:** A human-readable text block (not JSON):

```
Gene Profile: BRCA1 (Gene ID: 672)
=====================================
Full Name: BRCA1 DNA repair associated
Organism: Homo sapiens
Chromosome: 17 (17q21.31)
Gene Type: protein-coding

Summary:
This gene encodes a nuclear phosphoprotein that plays a role in
maintaining genomic stability and acts as a tumour suppressor...

Aliases: IRIS, PSCP, BRCAI, BRCC1, FANCS, RNF53

Associated Diseases:
  • Breast-ovarian cancer, familial 1
  • Fanconi anemia, complementation group S

Pathways:
  • DNA double-strand break repair
  • Homologous recombination

Data retrieved: 2025-01-15T10:30:00Z
Source: NCBI Gene (https://www.ncbi.nlm.nih.gov/gene/672)
```

---

### 5.2 Resource: `glossary://genomics/{term}`

**Purpose:** A local glossary of genomics and drug-discovery terminology, so Claude can explain results clearly to non-expert enterprise users (e.g., a biotech VP of Strategy who isn't a bench scientist).

**URI Template:** `glossary://genomics/{term}`

**Implementation:** Read from a local YAML file (`data/glossary/genomics.yaml`). No API call needed.

**Glossary YAML Structure:**

```yaml
gene_expression:
  term: "Gene Expression"
  definition: "The process by which information from a gene is used to synthesise a functional gene product, typically a protein."
  enterprise_context: "When assessing a therapeutic target, expression levels indicate where in the body the gene is active — relevant for drug delivery and side-effect prediction."

protein_coding:
  term: "Protein-coding Gene"
  definition: "A gene that encodes instructions for building a protein."
  enterprise_context: "Most drug targets are protein-coding genes, as the resulting proteins can be targeted by small molecules or biologics."

ortholog:
  term: "Ortholog"
  definition: "Genes in different species that evolved from a common ancestral gene."
  enterprise_context: "Relevant for preclinical research — if a drug target has a mouse ortholog, it can be studied in animal models."

pathway:
  term: "Biological Pathway"
  definition: "A series of molecular interactions and reactions that lead to a specific biological outcome."
  enterprise_context: "Understanding which pathways a target gene belongs to helps identify potential combination therapies and predict off-target effects."

# Include 15-20 terms total. Focus on terms that appear in your tool outputs.
# Suggested terms: gene_expression, protein_coding, ortholog, pathway,
# chromosome, map_location, gene_type, ncRNA, tumour_suppressor,
# oncogene, kinase, receptor, phenotype, genotype, variant,
# monogenic, polygenic, biomarker, druggable_target
```

**Return Format:** When Claude reads `glossary://genomics/pathway`, return:

```
Term: Biological Pathway
Definition: A series of molecular interactions and reactions that lead to a specific biological outcome.
Enterprise Context: Understanding which pathways a target gene belongs to helps identify potential combination therapies and predict off-target effects.
```

If term not found: Return a list of all available terms so Claude can pick the right one.

---

## 6. MCP Prompts — Detailed Specifications

### 6.1 Prompt: `target_assessment`

**Purpose:** A reusable prompt template for producing a comprehensive therapeutic target assessment — the kind of briefing a drug discovery analyst would present at a portfolio review meeting.

#### Arguments

```json
{
  "gene_name": {
    "type": "string",
    "description": "Gene name or symbol to assess (e.g., 'BRCA1', 'TP53')",
    "required": true
  },
  "disease_context": {
    "type": "string",
    "description": "Disease or therapeutic area for context (e.g., 'breast cancer', 'non-small cell lung cancer')",
    "required": false
  }
}
```

#### Generated Prompt

```
You are a genomics research assistant supporting a drug discovery team at a biotech company.

Your task: Produce a structured Therapeutic Target Assessment for the gene "{gene_name}"
{if disease_context: "in the context of {disease_context}"}.

Follow these steps using the available tools:

1. SEARCH: Use search_genes to find "{gene_name}" and identify the correct NCBI Gene ID.
2. PROFILE: Use get_gene_details with the Gene ID to retrieve the full gene profile.
3. EVIDENCE: Use get_literature with the Gene ID to find the 5 most recent relevant publications.
4. SYNTHESISE: Combine the above into a structured Target Assessment Report with these sections:

   ## Target Overview
   Gene symbol, full name, organism, chromosome location, gene type.

   ## Biological Function
   Plain-English summary of what this gene does, based on the gene profile summary.
   Define any technical terms for a non-specialist audience.

   ## Disease Relevance
   Known disease associations from the gene profile.
   {if disease_context: "Specifically address relevance to {disease_context}."}

   ## Pathway Context
   Pathways this gene participates in and what that implies for therapeutic intervention.

   ## Recent Evidence
   Summarise the top 3-5 recent publications, noting key findings relevant to
   therapeutic potential.

   ## Key Risks & Unknowns
   Based on the available data, note any gaps, concerns, or areas requiring
   further investigation.

   ## Recommendation
   A brief, balanced assessment of this gene's potential as a therapeutic target.

Format the report for a non-technical audience (e.g., VP of Strategy, portfolio
review committee). Avoid unnecessary jargon, and where technical terms are
required, provide brief plain-English explanations.
```

---

### 6.2 Prompt: `pipeline_comparison`

**Purpose:** A reusable prompt template for comparing multiple candidate therapeutic targets side by side — for pipeline prioritisation decisions.

#### Arguments

```json
{
  "gene_names": {
    "type": "string",
    "description": "Comma-separated gene names or symbols to compare (e.g., 'BRCA1, TP53, EGFR')",
    "required": true
  },
  "disease_context": {
    "type": "string",
    "description": "Disease or therapeutic area for context",
    "required": false
  }
}
```

#### Generated Prompt

```
You are a genomics research assistant supporting a drug discovery team at a biotech company.

Your task: Produce a Pipeline Comparison Report for the following candidate
therapeutic targets: {gene_names}
{if disease_context: "in the context of {disease_context}"}.

Follow these steps using the available tools:

1. SEARCH: For each gene in [{gene_names}], use search_genes to find the correct
   NCBI Gene ID.
2. COMPARE: Use compare_genes with all the Gene IDs to get a structured comparison.
3. EVIDENCE: Use get_literature for each gene to find recent publications.
4. SYNTHESISE: Combine the above into a Pipeline Comparison Report with these sections:

   ## Candidate Overview Table
   A side-by-side table of all candidates with: symbol, full name, chromosome,
   gene type, number of disease associations, number of recent publications.

   ## Individual Profiles
   A brief (3-4 sentence) profile of each gene's function and disease relevance.

   ## Comparative Analysis
   - Shared disease associations across candidates
   - Shared pathway involvement
   - Chromosomal co-location (if any)
   - Relative depth of evidence (publication volume)

   ## Strengths & Gaps by Candidate
   For each gene, 2-3 bullet points on strengths and 2-3 on gaps/risks.

   ## Recommendation Matrix
   A summary table: Gene | Strength of Evidence | Disease Relevance |
   Pathway Druggability | Overall Priority (High/Medium/Low)

Format for a portfolio review meeting audience. Be balanced and evidence-based.
Where data is limited, say so explicitly rather than speculating.
```

---

## 7. Data Layer — Detailed Specifications

### 7.1 NCBI Client (`ncbi_client.py`)

A single, reusable async HTTP client that all tools call through. This avoids duplicating API logic across tools.

**Responsibilities:**

- Construct Entrez API URLs with correct parameters
- Add `email` and `tool` headers to every request
- Handle rate limiting (max 3 requests/second — use `asyncio.sleep` if needed)
- Parse JSON responses (and XML for `efetch` if you implement that)
- Raise structured exceptions on API errors

**Key Functions:**

```python
async def search(db: str, term: str, max_results: int = 10) -> dict
async def summary(db: str, ids: list[str]) -> dict
async def fetch(db: str, id: str) -> str  # Returns raw XML for gene db
async def link(dbfrom: str, db: str, id: str, linkname: str) -> dict
```

---

### 7.2 SQLite Cache (`cache.py`)

**Purpose:** Cache API responses locally so repeated queries (especially within multi-tool prompt workflows) are instant and don't hit rate limits.

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS gene_cache (
    gene_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,          -- JSON string of the gene details
    retrieved_at TEXT NOT NULL,  -- ISO 8601 timestamp
    expires_at TEXT NOT NULL     -- retrieved_at + 7 days
);

CREATE TABLE IF NOT EXISTS literature_cache (
    gene_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,          -- JSON string of literature results
    retrieved_at TEXT NOT NULL,
    expires_at TEXT NOT NULL     -- retrieved_at + 1 day (literature updates more often)
);
```

**Logic:**

- On `get_gene_details`: check cache first → if valid, return cached → if stale/missing, call API, cache result, return
- On `get_literature`: same pattern, but with 1-day TTL instead of 7-day
- `search_genes`: do not cache searches (users expect fresh results when searching)
- `compare_genes`: no separate cache — it calls `get_gene_details` per gene, which caches individually

**Cache location:** `~/.mcp-genomics/cache.db` (user's home directory)

---

### 7.3 Glossary Files

- **Location:** `data/glossary/genomics.yaml`
- **Format:** As specified in Section 5.2
- **Size:** 15–20 terms. No more needed for the project to be effective.

---

## 8. Repo Structure

```
mcp-genomics/
│
├── README.md                          # The write-up (see Section 10)
├── pyproject.toml                     # Project config, dependencies, entry point
├── LICENSE                            # MIT
│
├── src/
│   └── mcp_genomics/
│       ├── __init__.py
│       ├── server.py                  # MCP server entry point & component registration
│       │
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── search_genes.py        # search_genes tool
│       │   ├── gene_details.py        # get_gene_details tool
│       │   ├── compare_genes.py       # compare_genes tool
│       │   └── literature.py          # get_literature tool
│       │
│       ├── resources/
│       │   ├── __init__.py
│       │   ├── gene_resource.py       # gene://ncbi/{id} resource handler
│       │   └── glossary_resource.py   # glossary://genomics/{term} resource handler
│       │
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── templates.py           # target_assessment & pipeline_comparison
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   └── ncbi_client.py         # NCBI Entrez API wrapper
│       │
│       └── data/
│           ├── __init__.py
│           └── cache.py               # SQLite caching layer
│
├── data/
│   └── glossary/
│       └── genomics.yaml              # Genomics glossary (15-20 terms)
│
├── tests/
│   ├── __init__.py
│   ├── test_search_genes.py           # Tests for search_genes tool
│   ├── test_gene_details.py           # Tests for get_gene_details tool
│   ├── test_compare_genes.py          # Tests for compare_genes tool
│   ├── test_literature.py             # Tests for get_literature tool
│   ├── test_ncbi_client.py            # Tests for the API client
│   ├── test_cache.py                  # Tests for caching layer
│   └── fixtures/
│       ├── gene_672_summary.json      # Cached NCBI response for BRCA1
│       ├── gene_7157_summary.json     # Cached NCBI response for TP53
│       ├── pubmed_brca1_links.json    # Cached elink response
│       └── pubmed_summaries.json      # Cached PubMed summaries
│
├── claude_desktop_config.json         # Example Claude Desktop MCP config
│
└── demo/
    └── screenshots/                   # Screenshots or GIF of it working in Claude Desktop
```

---

## 9. Test Suite — Detailed Specifications

### 9.1 Strategy

Tests use saved API response fixtures (in `tests/fixtures/`) so they run without hitting the real NCBI API. This makes them fast, deterministic, and offline-capable.

### 9.2 Test Categories

#### Unit Tests — Tool Logic

For each tool, test that given a known API response (loaded from fixture), the tool produces the expected output structure.

**`test_search_genes.py`:**

- `test_search_returns_structured_results` — Given a fixture `esearch` + `esummary` response for `"BRCA1 human"`, assert output contains a list of dicts with `gene_id`, `symbol`, `name`, `organism`, `chromosome`
- `test_search_no_results` — Given an empty `esearch` response, assert output contains a clear "no results" message
- `test_search_clamps_max_results` — Assert that `max_results=100` gets clamped to 50

**`test_gene_details.py`:**

- `test_details_returns_full_profile` — Given fixture for gene 672, assert all fields present (`symbol`, `name`, `organism`, `chromosome`, `summary`, `aliases`)
- `test_details_uses_cache` — Call twice, assert second call doesn't hit the API mock
- `test_details_invalid_id` — Assert a clear error for a nonexistent gene ID

**`test_compare_genes.py`:**

- `test_compare_two_genes` — Given fixtures for genes 672 and 7157, assert comparison table has correct structure
- `test_compare_identifies_shared_chromosome` — BRCA1 and TP53 are both on chr 17, assert this is detected
- `test_compare_minimum_two` — Assert error when only one gene ID provided

**`test_literature.py`:**

- `test_literature_returns_articles` — Given fixtures for `elink` + pubmed `esummary`, assert output contains articles with `title`, `authors`, `journal`, `date`, `pmid`, `url`
- `test_literature_no_articles` — Given empty `elink` response, assert clear message

#### Unit Tests — Infrastructure

- `test_ncbi_client.py`: Test URL construction, rate limit logic, error handling
- `test_cache.py`: Test insert, retrieve, expiry, stale-cache-fallback

#### Integration Test *(Optional — Requires Network)*

A single test marked `@pytest.mark.integration` that calls the real NCBI API for gene 672 (BRCA1) and asserts the response can be parsed. Not run in CI, but useful for validating the real API contract hasn't changed.

### 9.3 Fixtures

Save real API responses as JSON files in `tests/fixtures/`. To create them:

1. Make the real API calls once manually (e.g., in a notebook or script)
2. Save the raw JSON responses to files
3. Load these in tests with `json.load()`

This is standard practice and shows production engineering habits.

---

## 10. README Structure — Detailed Outline

This is the write-up that turns the project into a communication signal. Structure it as follows:

### 10.1 Header

```markdown
# mcp-genomics 🧬

An MCP server that gives Claude access to genomics intelligence —
built for biotech & pharma enterprise workflows.
```

### 10.2 Sections

1. **The Scenario** (3–4 sentences) — You're an FDE at a biotech customer. Analysts waste hours on manual gene research. You build this.
2. **What It Does** (bullet list)
   - Search genes across NCBI databases
   - Pull detailed gene profiles with disease and pathway data
   - Compare candidate therapeutic targets side by side
   - Surface recent PubMed evidence linked to any gene
   - Pre-built prompts for target assessment and pipeline comparison workflows
3. **Architecture** — the diagram from Section 2.1
4. **Quick Start** — 5 steps: Clone, install, configure Claude Desktop, run, try the demo query
5. **Tools Reference** — table: tool name, description, example input
6. **Resources Reference** — table: URI pattern, description
7. **Prompt Templates** — table: prompt name, what it does, arguments
8. **Design Decisions** *(this is the section that shows engineering judgment)*
   - Why deterministic tools for computation rather than letting Claude calculate
   - Why SQLite caching (rate limits, latency, offline resilience)
   - Why enterprise framing for a genomics project
   - Why resource + tool separation (context grounding vs. action)
9. **Testing** — how to run, what's covered
10. **What I'd Build Next** *(shows you think beyond MVP)*
    - Additional data sources (UniProt for protein data, Ensembl for variants)
    - SSE transport for remote deployment
    - Authentication layer for enterprise environments
    - Usage analytics and monitoring
11. **About** (2–3 sentences) — Your background: AI engineer, PhD in computational biology. Built to demonstrate MCP development for the biotech/pharma vertical.

---

## 11. Build Sequence

| Phase | What You Build | Time | Milestone |
|---|---|---|---|
| Phase 1: Skeleton | Repo scaffold, `pyproject.toml`, empty `server.py` that starts and connects to Claude Desktop. One dummy tool that returns `"hello"`. | ~1.5 hours | Claude Desktop shows your server as connected ✅ |
| Phase 2: API Client | `ncbi_client.py` with `search()` and `summary()` functions. Test with BRCA1. Save fixtures. | ~2 hours | You can call NCBI and get structured JSON back ✅ |
| Phase 3: First Tool | `search_genes` tool, fully wired. Test in Claude Desktop: *"Search for genes related to Alzheimer's disease"* | ~1.5 hours | Claude can search genes through your server ✅ |
| Phase 4: Details + Cache | `get_gene_details` tool + SQLite cache + `gene://` resource. | ~2 hours | Claude can deep-dive into any gene ✅ |
| Phase 5: Literature | `get_literature` tool, including `elink` and PubMed `esummary`. | ~1.5 hours | Claude can find papers for any gene ✅ |
| Phase 6: Compare | `compare_genes` tool. Pure Python on top of `get_gene_details`. | ~1.5 hours | Claude can compare targets side by side ✅ |
| Phase 7: Prompts + Glossary | Prompt templates + glossary YAML + glossary resource. | ~1.5 hours | Full multi-step workflows running ✅ |
| Phase 8: Tests | Test suite with fixtures for all tools. | ~2 hours | `pytest` passes, all green ✅ |
| Phase 9: README + Demo | Write-up, architecture diagram, screenshots/GIF. | ~2 hours | Repo is portfolio-ready ✅ |

**Total: ~15.5 hours across 2 weekends**

---

## 12. Claude Desktop Configuration

To connect the server to Claude Desktop, add this to your Claude Desktop config file (`~/Library/Application Support/Claude/claude_desktop_config.json` on Mac):

```json
{
  "mcpServers": {
    "mcp-genomics": {
      "command": "python",
      "args": ["-m", "mcp_genomics.server"],
      "env": {
        "NCBI_EMAIL": "your.email@example.com"
      }
    }
  }
}
```

Include this file in your repo as `claude_desktop_config.json` (with a placeholder email) so anyone cloning the repo knows exactly how to set it up.

---

## 13. Demo Queries to Record

When you take screenshots or record a GIF for the README, use these queries to showcase the full range:

1. **Simple search:** *"Find genes associated with Parkinson's disease"*
2. **Deep dive:** *"Tell me everything about the LRRK2 gene"*
3. **Literature:** *"What's been published recently about EGFR?"*
4. **Comparison:** *"Compare BRCA1, BRCA2, and TP53 as therapeutic targets for breast cancer"*
5. **Full workflow (`target_assessment` prompt):** *"Produce a target assessment for KRAS in the context of non-small cell lung cancer"*

> Query 5 is the showstopper — it chains all tools and produces an enterprise-ready document.

---

## 14. CV Bullet (Final)

Once complete, add this to your CV:

> **Open-Source MCP Server for Genomics Intelligence** | [GitHub link]
>
> Built an MCP server (Anthropic Python SDK) designed for biotech/pharma enterprise workflows: therapeutic target search, gene profiling, cross-target comparison, and evidence retrieval via NCBI databases — with MCP resources for data grounding and domain glossaries, and prompt templates for multi-step target assessment and pipeline review workflows. Includes SQLite caching and an automated test suite. Write-up: [link].