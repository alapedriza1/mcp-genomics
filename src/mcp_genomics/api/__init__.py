"""NCBI Entrez API integration layer."""

from mcp_genomics.api.ncbi_client import NCBIClient, NCBIClientError

__all__ = ["NCBIClient", "NCBIClientError"]
