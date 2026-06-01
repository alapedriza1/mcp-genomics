"""
MCP prompt templates: target_assessment & pipeline_comparison

Reusable multi-step workflow templates that guide Claude through
structured genomics analyses using the available tools.
"""


def target_assessment_prompt(
    gene_name: str,
    disease_context: str | None = None,
) -> str:
    """
    Generate a therapeutic target assessment prompt.

    Guides Claude through: search → profile → literature → synthesise
    into a structured report for a portfolio review audience.

    Args:
        gene_name: Gene name or symbol to assess (e.g., "BRCA1", "TP53").
        disease_context: Optional disease or therapeutic area for context.

    Returns:
        The full prompt string for Claude to follow.
    """
    disease_line = ""
    if disease_context:
        disease_line = f' in the context of {disease_context}'

    disease_section = ""
    if disease_context:
        disease_section = f'\n    Specifically address relevance to {disease_context}.'

    return f"""You are a genomics research assistant supporting a drug discovery team at a biotech company.

Your task: Produce a structured Therapeutic Target Assessment for the gene "{gene_name}"{disease_line}.

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
   Known disease associations from the gene profile.{disease_section}

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
required, provide brief plain-English explanations."""


def pipeline_comparison_prompt(
    gene_names: str,
    disease_context: str | None = None,
) -> str:
    """
    Generate a pipeline comparison prompt for multiple gene candidates.

    Guides Claude through: search each gene → compare → literature → synthesise
    into a side-by-side comparison report for pipeline prioritisation.

    Args:
        gene_names: Comma-separated gene names or symbols (e.g., "BRCA1, TP53, EGFR").
        disease_context: Optional disease or therapeutic area for context.

    Returns:
        The full prompt string for Claude to follow.
    """
    disease_line = ""
    if disease_context:
        disease_line = f'\nin the context of {disease_context}'

    return f"""You are a genomics research assistant supporting a drug discovery team at a biotech company.

Your task: Produce a Pipeline Comparison Report for the following candidate
therapeutic targets: {gene_names}{disease_line}.

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
Where data is limited, say so explicitly rather than speculating."""
