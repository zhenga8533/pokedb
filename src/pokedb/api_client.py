import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter, Retry

from .utils import SERVER_ERROR_CODES, get_cache_path

logger = logging.getLogger(__name__)


class ApiClient:
    """
    A memoized and file-cached API client for making requests to the PokéAPI.

    This client provides:
    - In-memory caching for repeated requests within the same session
    - File-based caching with configurable expiration
    - Automatic retry logic for server errors
    - Configurable timeout settings
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the ApiClient with configuration settings.

        Args:
            config: Configuration dictionary containing:
                - timeout: Request timeout in seconds (default: 15)
                - parser_cache_dir: Directory for cache files (optional)
                - cache_expires: Cache expiration time in seconds (optional)
                - max_retries: Maximum number of retry attempts (default: 3)
        """
        self._session = self._setup_session(config)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.timeout: int = config.get("timeout", 15)
        self.cache_dir: Optional[str] = config.get("parser_cache_dir")
        self.cache_expires: Optional[int] = config.get("cache_expires")

        if self.cache_dir:
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Cache directory initialized at {self.cache_dir}")

    def _setup_session(self, config: Dict[str, Any]) -> requests.Session:
        """
        Creates a requests Session with automatic retry logic for server errors.

        Args:
            config: Configuration dictionary

        Returns:
            Configured requests.Session instance
        """
        session = requests.Session()
        retries = Retry(
            total=config.get("max_retries", 3),
            backoff_factor=0.5,
            status_forcelist=SERVER_ERROR_CODES,
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session

    def get(self, url: str) -> Dict[str, Any]:
        """
        Fetches JSON data from a URL, using both in-memory and file-based caches.

        The caching strategy is:
        1. Check in-memory cache first (fastest)
        2. Check file cache if enabled and not expired
        3. Make HTTP request if no valid cache exists
        4. Update both caches with the response

        Args:
            url: The API endpoint URL to fetch

        Returns:
            The JSON response as a dictionary

        Raises:
            requests.HTTPError: If the HTTP request fails
            requests.Timeout: If the request times out
            json.JSONDecodeError: If the response is not valid JSON
        """
        # Check in-memory cache first
        if url in self._cache:
            logger.debug(f"Cache hit (memory): {url}")
            return self._cache[url]

        # Check file cache if enabled
        cache_file_path: Optional[Path] = None
        if self.cache_dir and self.cache_expires is not None:
            cache_file_path = get_cache_path(url, self.cache_dir)

            if cache_file_path.exists():
                file_mod_time = cache_file_path.stat().st_mtime
                cache_age = time.time() - file_mod_time

                if cache_age < self.cache_expires:
                    logger.debug(f"Cache hit (file): {url}")
                    with open(cache_file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._cache[url] = data
                        return data
                else:
                    logger.debug(f"Cache expired for: {url}")

        # Fetch from API
        logger.debug(f"Fetching from API: {url}")
        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        # Update in-memory cache
        self._cache[url] = data

        # Update file cache if enabled
        if cache_file_path:
            with open(cache_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

        return data
