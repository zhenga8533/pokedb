from typing import Any, Dict

import requests
from requests.adapters import HTTPAdapter, Retry


class ApiClient:
    """A memoized API client for making requests to the PokéAPI."""

    def __init__(self, config: Dict[str, Any]):
        """Initializes the ApiClient."""
        self._session = self._setup_session(config)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.timeout = config.get("timeout", 15)

    def _setup_session(self, config: Dict[str, Any]) -> requests.Session:
        """Creates a requests Session with automatic retry logic."""
        session = requests.Session()
        retries = Retry(
            total=config.get("max_retries", 3),
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session

    def get(self, url: str) -> Dict[str, Any]:
        """Fetches JSON data from a URL, using a cache to avoid redundant requests."""
        if url in self._cache:
            return self._cache[url]

        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        self._cache[url] = data
        return data
