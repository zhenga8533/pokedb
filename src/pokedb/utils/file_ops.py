"""File operations and caching utilities."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict


def get_cache_path(url: str, cache_dir: str) -> Path:
    """
    Generates a cache file path for a given URL using MD5 hashing.

    Args:
        url: The URL to generate a cache path for
        cache_dir: The directory where cache files are stored

    Returns:
        A Path object pointing to the cache file location

    Raises:
        ValueError: If cache_dir is not provided
    """
    if not cache_dir:
        raise ValueError("cache_dir must be provided to generate a cache path.")

    hashed_url = hashlib.md5(url.encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{hashed_url}.json"


def write_json_file(output_dir: str, filename: str, data: Dict[str, Any]) -> Path:
    """
    Writes data to a JSON file with proper formatting and snake_case key transformation.

    Args:
        output_dir: The directory where the file should be written
        filename: The name of the file (without .json extension)
        data: The data dictionary to write

    Returns:
        Path to the written file
    """
    from .text_utils import transform_keys_to_snake_case

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    file_path = output_path / f"{filename}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(transform_keys_to_snake_case(data), f, indent=4, ensure_ascii=False)

    return file_path
