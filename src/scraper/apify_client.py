"""
Apify API client for LinkedIn job scraping.
Uses the actor: bebity/linkedin-jobs-scraper
"""

import asyncio
from typing import Optional

import httpx
from loguru import logger

from shared.config import Settings, get_settings
from shared.models import ApifyJobResult


class ApifyClient:
    """Client for Apify LinkedIn Jobs Scraper API (bebity/linkedin-jobs-scraper)."""

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
            self._client = httpx.AsyncClient(timeout=600.0)
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def run_actor_sync(
        self,
        title: str,
        location: str,
        max_jobs: int = 100,
        timeout_secs: int = 300,
        date_posted: str = "past-week",
    ) -> list[ApifyJobResult]:
        """
        Run the LinkedIn Jobs Scraper actor synchronously and return results directly.
        Uses the run-sync-get-dataset-items endpoint for simpler operation.

        Args:
            title: Job title to search for (e.g., "Security Engineer")
            location: Location to search in (e.g., "Switzerland")
            max_jobs: Maximum number of jobs to scrape (uses 'rows' parameter)
            timeout_secs: Timeout in seconds
            date_posted: Date filter - "past-24h", "past-week", "past-month", or None for all

        Returns:
            List of job results
        """
        client = await self._get_client()

        # Actor input configuration for LinkedIn scraper
        # Using title and location parameters for accurate results
        actor_input = {
            "title": title,
            "location": location,
            "rows": max_jobs,
        }

        # Add date filter if specified (LinkedIn uses f_TPR parameter)
        # r86400 = past 24 hours, r604800 = past week, r2592000 = past month
        if date_posted:
            date_filters = {
                "past-24h": "r86400",
                "past-week": "r604800",
                "past-month": "r2592000",
            }
            if date_posted in date_filters:
                actor_input["publishedAt"] = date_filters[date_posted]
                logger.info(f"Date filter: {date_posted}")

        # Use sync endpoint for simpler operation
        sync_url = f"{self.base_url}/acts/{self.actor_id}/run-sync-get-dataset-items"
        logger.info(f"Starting Apify LinkedIn Jobs Scraper (sync)")
        logger.info(f"Job title: {title}")
        logger.info(f"Location: {location}")
        logger.info(f"Max jobs: {max_jobs}")

        response = await client.post(
            sync_url,
            headers=self.headers,
            json=actor_input,
            params={"timeout": timeout_secs},
        )
        response.raise_for_status()

        items = response.json()
        logger.info(f"Fetched {len(items)} jobs from LinkedIn")

        return self._parse_results(items)

    async def run_actor(
        self,
        search_url: str,
        max_jobs: int = 100,
        wait_for_finish: bool = True,
        timeout_secs: int = 600,
    ) -> list[ApifyJobResult]:
        """
        Run the LinkedIn Jobs Scraper actor asynchronously.

        Args:
            search_url: LinkedIn jobs search URL
            max_jobs: Maximum number of jobs to scrape
            wait_for_finish: Wait for actor to complete
            timeout_secs: Timeout in seconds

        Returns:
            List of job results
        """
        client = await self._get_client()

        # Actor input configuration for LinkedIn scraper
        actor_input = {
            "searchUrl": search_url,
            "rows": max_jobs,
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

        return self._parse_results(items)

    def _parse_results(self, items: list[dict]) -> list[ApifyJobResult]:
        """Parse raw items into ApifyJobResult objects."""
        results = []
        for item in items:
            try:
                result = ApifyJobResult.model_validate(item)
                if result.id and result.title:  # Skip invalid entries
                    results.append(result)
            except Exception as e:
                logger.warning(f"Failed to parse job item: {e}")

        return results

    async def run_multi_title_search(
        self,
        titles: list[str],
        location: str,
        jobs_per_title: int = 10,
        max_total_jobs: int = 50,
        delay_between_searches: float = 2.0,
    ) -> list[ApifyJobResult]:
        """
        Search for multiple job titles with deduplication and rate limiting.

        Args:
            titles: List of job titles to search for
            location: Location to search in
            jobs_per_title: Max jobs to fetch per title
            max_total_jobs: Maximum total jobs to return
            delay_between_searches: Seconds to wait between API calls

        Returns:
            Deduplicated list of job results
        """
        all_results: list[ApifyJobResult] = []
        seen_ids: set[str] = set()

        logger.info(f"Starting multi-title search: {len(titles)} titles")
        logger.info(f"Location: {location}, Jobs per title: {jobs_per_title}")

        for i, title in enumerate(titles):
            if len(all_results) >= max_total_jobs:
                logger.info(f"Reached max jobs limit ({max_total_jobs}), stopping")
                break

            logger.info(f"[{i+1}/{len(titles)}] Searching: {title}")

            try:
                results = await self.run_actor_sync(
                    title=title,
                    location=location,
                    max_jobs=jobs_per_title,
                )

                # Deduplicate
                new_count = 0
                for result in results:
                    if result.id and result.id not in seen_ids:
                        seen_ids.add(result.id)
                        all_results.append(result)
                        new_count += 1

                        if len(all_results) >= max_total_jobs:
                            break

                logger.info(f"    Found {len(results)} jobs, {new_count} new (deduplicated)")

            except Exception as e:
                logger.error(f"    Error searching '{title}': {e}")

            # Rate limiting - delay between searches (except last one)
            if i < len(titles) - 1 and len(all_results) < max_total_jobs:
                await asyncio.sleep(delay_between_searches)

        logger.info(f"Multi-title search complete: {len(all_results)} unique jobs")
        return all_results

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
