import asyncio
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from receipt_api.config import get_settings

logger = structlog.get_logger(__name__)


class GitHubClient:
    """Async GitHub REST client with ETag caching and rate-limit backoff."""

    def __init__(self, token: Optional[str] = None):
        self.settings = get_settings()
        self.token = token or self.settings.github_token
        self._etags: Dict[str, str] = {}
        self._cache: Dict[str, Any] = {}

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Receipt-Verification-Engine/1.0",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self.http_client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers=headers,
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=30.0),
        )

    async def close(self) -> None:
        await self.http_client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Fetch endpoint with ETag caching and rate-limit handling."""
        headers = {}
        cache_key = f"{endpoint}:{json.dumps(params or {}, sort_keys=True)}"

        if cache_key in self._etags:
            headers["If-None-Match"] = self._etags[cache_key]

        response = await self.http_client.get(endpoint, params=params, headers=headers)

        if response.status_code == 304:
            return self._cache[cache_key]

        if response.status_code == 403 and "rate limit" in response.text.lower():
            reset_time = int(response.headers.get("x-ratelimit-reset", "0"))
            logger.warning("github_rate_limited", reset_time=reset_time)
            await asyncio.sleep(5)
            response.raise_for_status()

        response.raise_for_status()
        data = response.json()

        if "etag" in response.headers:
            self._etags[cache_key] = response.headers["etag"]
            self._cache[cache_key] = data

        return data

    async def get_paginated(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None, per_page: int = 50
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Iterate through pages for paginated GitHub endpoints."""
        current_page = 1
        query_params = dict(params or {})
        query_params["per_page"] = per_page

        while True:
            query_params["page"] = current_page
            try:
                page_data = await self.get(endpoint, params=query_params)
            except Exception as e:
                logger.warning("github_pagination_ended", page=current_page, error=str(e))
                break

            if not isinstance(page_data, list) or len(page_data) == 0:
                break

            for item in page_data:
                yield item

            if len(page_data) < per_page:
                break

            current_page += 1
