import hashlib
import json
import os
import time
from typing import Any, Dict

import requests
from requests.adapters import HTTPAdapter, Retry


class ApiClient:
    """A memoized and file-cached API client for making requests to the PokéAPI."""

    def __init__(self, config: Dict[str, Any]):
        """Initializes the ApiClient."""
        self._session = self._setup_session(config)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.timeout = config.get("timeout", 15)
        self.cache_dir = config.get("parser_cache_dir")
        self.cache_expires = config.get("cache_expires")

        if self.cache_dir:
            os.makedirs(self.cache_dir, exist_ok=True)

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

    def _get_cache_path(self, url: str) -> str:
        """Generates a file path for a given URL."""
        hashed_url = hashlib.md5(url.encode("utf-8")).hexdigest()
        if not self.cache_dir:
            raise ValueError("cache_dir must be set to generate a cache path.")
        return os.path.join(self.cache_dir, f"{hashed_url}.json")

    def get(self, url: str) -> Dict[str, Any]:
        """Fetches JSON data from a URL, using both in-memory and file-based caches."""
        if url in self._cache:
            return self._cache[url]

        cache_path = None
        if self.cache_dir and self.cache_expires is not None:
            cache_path = self._get_cache_path(url)
            if os.path.exists(cache_path):
                file_mod_time = os.path.getmtime(cache_path)
                if time.time() - file_mod_time < self.cache_expires:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._cache[url] = data
                        return data

        response = self._session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        self._cache[url] = data

        if cache_path:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

        return data
