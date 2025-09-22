from typing import Any, Dict

import requests
from requests.adapters import HTTPAdapter, Retry


class ApiClient:
    """A memoized API client for making requests to the PokéAPI."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the ApiClient.

        Args:
            config (Dict[str, Any]): The application configuration.
        """
        self._session = self._setup_session(config)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.timeout = config.get("timeout", 15)

    def _setup_session(self, config: Dict[str, Any]) -> requests.Session:
        """
        Creates a requests Session with automatic retry logic.

        Args:
            config (Dict[str, Any]): The application configuration dictionary.

        Returns:
            requests.Session: A requests Session object configured with retries.
        """
        session = requests.Session()
        retries = Retry(
            total=config.get("max_retries", 3),
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))
        return session

    def get(self, url: str) -> Dict[str, Any]:
        """
        Fetches JSON data from a URL, using a cache to avoid redundant requests.

        Args:
            url (str): The URL to fetch data from.

        Returns:
            Dict[str, Any]: The JSON response as a dictionary.

        Raises:
            requests.exceptions.RequestException: If the request fails after all retries.
        """
        if url in self._cache:
            return self._cache[url]

        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        self._cache[url] = data
        return data
