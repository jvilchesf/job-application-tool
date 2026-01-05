"""
Apify API client for LinkedIn job scraping.
Uses the actor: KfYqwOhOXqkqO4DF8
"""

import asyncio
from typing import Any, Optional

import httpx
from loguru import logger

from shared.config import Settings, get_settings
from shared.models import ApifyJobResult


class ApifyClient:
    """Client for Apify LinkedIn Jobs Scraper API."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.apify_base_url
        self.actor_id = self.settings.apify_actor_id
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def headers(self) -> dict[str, str]:
        """Get request headers with auth token."""
        return {
            "Authorization": f"Bearer {self.settings.apify_api_token.get_secret_value()}",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=300.0)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def run_actor(
        self,
        search_url: str,
        max_jobs: int = 100,
        wait_for_finish: bool = True,
        timeout_secs: int = 600,
    ) -> list[ApifyJobResult]:
        """
        Run the LinkedIn Jobs Scraper actor and return results.

        Args:
            search_url: LinkedIn jobs search URL
            max_jobs: Maximum number of jobs to scrape
            wait_for_finish: Wait for actor to complete
            timeout_secs: Timeout in seconds

        Returns:
            List of job results
        """
        client = await self._get_client()

        # Actor input configuration
        actor_input = {
            "searchUrl": search_url,
            "maxItems": max_jobs,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        # Start actor run
        run_url = f"{self.base_url}/acts/{self.actor_id}/runs"
        logger.info(f"Starting Apify actor: {self.actor_id}")
        logger.debug(f"Actor input: {actor_input}")

        response = await client.post(
            run_url,
            headers=self.headers,
            json=actor_input,
        )
        response.raise_for_status()

        run_data = response.json()["data"]
        run_id = run_data["id"]
        logger.info(f"Actor run started: {run_id}")

        if not wait_for_finish:
            return []

        # Poll for completion
        return await self._wait_for_results(run_id, timeout_secs)

    async def _wait_for_results(
        self, run_id: str, timeout_secs: int
    ) -> list[ApifyJobResult]:
        """Wait for actor run to complete and fetch results."""
        client = await self._get_client()
        status_url = f"{self.base_url}/actor-runs/{run_id}"

        elapsed = 0
        poll_interval = 10

        while elapsed < timeout_secs:
            response = await client.get(status_url, headers=self.headers)
            response.raise_for_status()

            run_data = response.json()["data"]
            status = run_data["status"]

            logger.info(f"Actor run status: {status} (elapsed: {elapsed}s)")

            if status == "SUCCEEDED":
                return await self._fetch_dataset(run_data["defaultDatasetId"])
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Actor run failed with status: {status}")

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Actor run timed out after {timeout_secs}s")

    async def _fetch_dataset(self, dataset_id: str) -> list[ApifyJobResult]:
        """Fetch results from actor's default dataset."""
        client = await self._get_client()

        dataset_url = f"{self.base_url}/datasets/{dataset_id}/items"
        logger.info(f"Fetching dataset: {dataset_id}")

        response = await client.get(
            dataset_url,
            headers=self.headers,
            params={"format": "json"},
        )
        response.raise_for_status()

        items = response.json()
        logger.info(f"Fetched {len(items)} jobs from dataset")

        results = []
        for item in items:
            try:
                result = ApifyJobResult.model_validate(item)
                if result.id and result.title:  # Skip invalid entries
                    results.append(result)
            except Exception as e:
                logger.warning(f"Failed to parse job item: {e}")

        return results

    async def get_last_run_results(self) -> list[ApifyJobResult]:
        """Get results from the last successful actor run."""
        client = await self._get_client()

        # Get last run
        runs_url = f"{self.base_url}/acts/{self.actor_id}/runs"
        response = await client.get(
            runs_url,
            headers=self.headers,
            params={"status": "SUCCEEDED", "limit": 1},
        )
        response.raise_for_status()

        runs = response.json()["data"]["items"]
        if not runs:
            logger.warning("No successful runs found")
            return []

        last_run = runs[0]
        return await self._fetch_dataset(last_run["defaultDatasetId"])
