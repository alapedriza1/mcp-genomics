"""
NCBI Entrez API async client with rate limiting and retry logic.

Provides wrappers for esearch, esummary, efetch, and elink endpoints.
Rate-limited to 3 requests/second per NCBI guidelines for keyless access.

Caching is handled separately by the data.cache module — this client
is purely responsible for HTTP transport and Entrez protocol.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ENTREZ_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Rate limit: 3 requests per second (NCBI guideline without API key)
RATE_LIMIT_RPS = 3

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds; exponential: 1s, 2s, 4s


class RateLimiter:
    """Token-bucket rate limiter for async requests."""

    def __init__(self, rps: float = RATE_LIMIT_RPS):
        self._interval = 1.0 / rps
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._interval:
                await asyncio.sleep(self._interval - elapsed)
            self._last_request_time = time.monotonic()


class NCBIClientError(Exception):
    """Raised when an NCBI API request fails after retries."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NCBIClient:
    """
    Async client for NCBI Entrez E-utilities.

    Provides low-level wrappers for esearch, esummary, efetch, and elink.
    Higher-level tool logic and caching live in the tools/ and data/ packages.

    Usage:
        async with NCBIClient() as client:
            results = await client.esearch("gene", "BRCA1 human")
    """

    def __init__(
        self,
        email: str | None = None,
        api_key: str | None = None,
        tool_name: str = "mcp-genomics",
    ):
        self._email = email
        self._api_key = api_key
        self._tool_name = tool_name
        self._rate_limiter = RateLimiter(
            rps=10 if api_key else RATE_LIMIT_RPS
        )
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "NCBIClient":
        self._client = httpx.AsyncClient(
            base_url=ENTREZ_BASE_URL,
            timeout=httpx.Timeout(30.0),
            headers={"User-Agent": f"{self._tool_name}/0.1.0"},
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _base_params(self) -> dict[str, str]:
        """Common parameters for all Entrez requests."""
        params: dict[str, str] = {"tool": self._tool_name}
        if self._email:
            params["email"] = self._email
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    async def _request_raw(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        """
        Make a rate-limited, retrying GET request to an Entrez endpoint.

        Returns the raw httpx.Response for the caller to parse
        (as JSON, XML, or text depending on the endpoint).

        Args:
            endpoint: E-utility endpoint path (e.g., "esearch.fcgi")
            params: Query parameters (merged with base params)

        Returns:
            Raw httpx.Response object

        Raises:
            NCBIClientError: After all retries are exhausted
        """
        if self._client is None:
            raise NCBIClientError(
                "Client not initialised. Use 'async with NCBIClient()' context."
            )

        full_params = {**self._base_params(), **params}

        # Retry loop with exponential backoff
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            await self._rate_limiter.acquire()
            try:
                response = await self._client.get(f"/{endpoint}", params=full_params)

                if response.status_code == 429:
                    # Rate limited by server — back off aggressively
                    wait = RETRY_BACKOFF_BASE * (2 ** attempt) * 2
                    logger.warning("Rate limited (429). Retrying in %.1fs...", wait)
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 500:
                    # Server error — retry
                    wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Server error %d. Retrying in %.1fs...",
                        response.status_code,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response

            except httpx.TimeoutException as e:
                last_error = e
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning(
                    "Timeout on attempt %d. Retrying in %.1fs...", attempt + 1, wait
                )
                await asyncio.sleep(wait)

            except httpx.HTTPStatusError as e:
                # Client errors (4xx except 429) — don't retry
                raise NCBIClientError(
                    f"HTTP {e.response.status_code}: {e.response.text[:200]}",
                    status_code=e.response.status_code,
                ) from e

            except httpx.RequestError as e:
                last_error = e
                wait = RETRY_BACKOFF_BASE * (2 ** attempt)
                logger.warning("Request error on attempt %d: %s", attempt + 1, str(e))
                await asyncio.sleep(wait)

        raise NCBIClientError(
            f"Request to {endpoint} failed after {MAX_RETRIES} retries: {last_error}"
        )

    async def _request_json(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> dict:
        """
        Make a request and parse the response as JSON.

        Args:
            endpoint: E-utility endpoint path
            params: Query parameters (retmode=json added automatically)

        Returns:
            Parsed JSON response dict
        """
        params = {**params, "retmode": "json"}
        response = await self._request_raw(endpoint, params)
        return response.json()

    async def _request_xml(
        self,
        endpoint: str,
        params: dict[str, Any],
    ) -> str:
        """
        Make a request and return the response as raw XML text.

        Args:
            endpoint: E-utility endpoint path
            params: Query parameters (retmode=xml added automatically)

        Returns:
            Raw XML response string
        """
        params = {**params, "retmode": "xml"}
        response = await self._request_raw(endpoint, params)
        return response.text

    # ─── E-utility Wrappers ───────────────────────────────────────────────

    async def esearch(
        self,
        db: str,
        term: str,
        retmax: int = 20,
    ) -> dict:
        """
        Search an NCBI database and return matching IDs.

        Args:
            db: Database name (e.g., "gene", "pubmed")
            term: Search query string
            retmax: Maximum number of IDs to return

        Returns:
            Dict with 'idlist', 'count', 'retmax', 'querytranslation'
        """
        params = {"db": db, "term": term, "retmax": str(retmax)}
        response = await self._request_json("esearch.fcgi", params)
        return response.get("esearchresult", {})

    async def esummary(
        self,
        db: str,
        ids: list[str],
    ) -> list[dict]:
        """
        Fetch document summaries for a list of IDs.

        Args:
            db: Database name
            ids: List of database UIDs

        Returns:
            List of summary dicts for each ID
        """
        if not ids:
            return []

        params = {"db": db, "id": ",".join(ids)}
        response = await self._request_json("esummary.fcgi", params)

        result = response.get("result", {})
        uid_list = result.get("uids", [])
        return [result[uid] for uid in uid_list if uid in result]

    async def efetch(
        self,
        db: str,
        ids: list[str],
        rettype: str = "docsum",
        retmode: str = "json",
    ) -> dict:
        """
        Fetch full records from an NCBI database (JSON mode).

        Args:
            db: Database name
            ids: List of database UIDs
            rettype: Return type (e.g., "docsum", "gene_table")
            retmode: Return mode ("json", "xml", "text")

        Returns:
            Parsed response dict
        """
        if not ids:
            return {}

        params = {
            "db": db,
            "id": ",".join(ids),
            "rettype": rettype,
            "retmode": retmode,
        }
        response = await self._request_raw("efetch.fcgi", params)
        return response.json()

    async def efetch_xml(
        self,
        db: str,
        gene_id: str,
    ) -> str:
        """
        Fetch the full XML record for a gene.

        The gene database's efetch endpoint only returns XML (no JSON option).
        Use xml.etree.ElementTree to parse the returned string.

        Args:
            db: Database name (typically "gene")
            gene_id: Single gene UID to fetch

        Returns:
            Raw XML string of the full gene record
        """
        params = {"db": db, "id": gene_id}
        return await self._request_xml("efetch.fcgi", params)

    async def elink(
        self,
        dbfrom: str,
        db: str,
        ids: list[str],
        linkname: str | None = None,
    ) -> list[str]:
        """
        Find related records across NCBI databases.

        Args:
            dbfrom: Source database
            db: Target database
            ids: Source UIDs
            linkname: Specific link name (e.g., "gene_pubmed")

        Returns:
            List of linked UIDs in the target database
        """
        if not ids:
            return []

        params = {
            "dbfrom": dbfrom,
            "db": db,
            "id": ",".join(ids),
            "cmd": "neighbor",
        }
        if linkname:
            params["linkname"] = linkname

        response = await self._request_json("elink.fcgi", params)

        # Parse linked IDs from the response structure
        linked_ids: list[str] = []
        linksets = response.get("linksets", [])
        for linkset in linksets:
            linksetdbs = linkset.get("linksetdbs", [])
            for linksetdb in linksetdbs:
                links = linksetdb.get("links", [])
                linked_ids.extend(str(link) for link in links)

        return linked_ids
