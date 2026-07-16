import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag

from .config import Config, load_config
from .utils import (
    ScraperError,
    get_cache_path,
    parse_gen_range,
    write_json_atomic,
)

logger = logging.getLogger(__name__)

RETRY_DELAY_SECONDS = 5
SCRAPER_CACHE_VERSION = 2


def scrape_pokemon_changes(
    pokemon_name: str, config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Scrapes Pokémon DB for all historical changes for a specific Pokémon.

    This function fetches generation-specific stat and ability changes from PokemonDB.net,
    which are not available through the PokéAPI. It includes file-based caching.

    Args:
        pokemon_name: The name of the Pokémon to scrape changes for

    Returns:
        A dictionary containing:
        - metadata: Dict with 'name' and 'source' keys
        - changes: List of change dictionaries with 'generations' and 'change' keys

    Examples:
        >>> scrape_pokemon_changes("pikachu")
        {'metadata': {'name': 'pikachu', 'source': '...'}, 'changes': [...]}
    """
    active_config = config if config is not None else load_config()
    cache_dir = active_config.scraper_cache_dir
    cache_expires = active_config.cache_expires
    max_retries = active_config.max_retries
    request_timeout = active_config.timeout

    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

    url = f"https://pokemondb.net/pokedex/{pokemon_name.lower()}"
    cache_file_path: Optional[Path] = None

    # Check cache
    if cache_dir:
        cache_file_path = get_cache_path(url, cache_dir)
        if cache_file_path.exists():
            file_mod_time = cache_file_path.stat().st_mtime
            if cache_expires is None or time.time() - file_mod_time < cache_expires:
                logger.debug(f"Cache hit for {pokemon_name}")
                try:
                    with cache_file_path.open("r", encoding="utf-8") as cache_file:
                        cached_data = json.load(cache_file)
                    if isinstance(cached_data, dict) and (
                        cached_data.get("metadata", {}).get("schema_version")
                        == SCRAPER_CACHE_VERSION
                    ):
                        return cached_data
                    logger.info("Refreshing outdated scraper cache for %s", pokemon_name)
                except (OSError, json.JSONDecodeError) as error:
                    logger.warning(
                        f"Ignoring unreadable cache entry {cache_file_path}: {error}"
                    )

    # Fetch HTML from PokemonDB
    all_changes: List[Dict[str, Any]] = []
    unsupported_changes: List[str] = []
    soup: Optional[BeautifulSoup] = None

    for attempt in range(max_retries + 1):
        try:
            logger.debug(
                f"Scraping {pokemon_name} (attempt {attempt + 1}/{max_retries + 1})"
            )
            response = requests.get(url, timeout=request_timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")
            break
        except requests.RequestException as e:
            if attempt < max_retries:
                logger.warning(
                    f"Scraping attempt {attempt + 1} failed for {pokemon_name}, retrying..."
                )
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(
                    f"Failed to scrape {url} after {max_retries + 1} attempts: {e}"
                )
                raise ScraperError(f"Failed to scrape {url}") from e

    if not soup:
        raise ScraperError(f"No HTML was returned for {url}")

    # Parse the changes section
    try:
        changes_header = next(
            (
                h
                for h in soup.find_all("h2")
                if isinstance(h, Tag)
                and h.get_text(" ", strip=True).lower().endswith(" changes")
            ),
            None,
        )
        if not changes_header:
            logger.debug(f"No changes section found for {pokemon_name}")
            empty_result = {
                "metadata": {
                    "name": pokemon_name,
                    "source": url,
                    "schema_version": SCRAPER_CACHE_VERSION,
                },
                "changes": [],
                "unsupported_changes": [],
            }
            if cache_file_path:
                write_json_atomic(cache_file_path, empty_result)
            return empty_result

        changes_list = changes_header.find_next_sibling("ul")
        if not isinstance(changes_list, Tag):
            raise ScraperError(f"Changes section has an unexpected format at {url}")

        rules = [
            ("does not have", _parse_ability_removal),  # Check negative ability changes first
            ("ability", _parse_ability),
            ("type", _parse_types),
            ("base experience yield", _parse_simple_stat("base_experience")),
            ("base friendship value", _parse_simple_stat("base_happiness")),
            ("catch rate", _parse_simple_stat("capture_rate")),
            ("evs", _parse_ev_yield),
            ("base special stat", _parse_special_stat),
            ("base hp", _parse_base_stat("hp")),
            ("base attack", _parse_base_stat("attack")),
            ("base defense", _parse_base_stat("defense")),
            ("base special attack", _parse_base_stat("special-attack")),
            ("base special defense", _parse_base_stat("special-defense")),
            ("base speed", _parse_base_stat("speed")),
        ]

        for li in changes_list.find_all("li"):
            if not isinstance(li, Tag):
                continue

            text = li.get_text()
            gen_abbr = li.find("abbr")
            if not gen_abbr:
                unsupported_changes.append(" ".join(text.split()))
                continue

            generations = parse_gen_range(gen_abbr.get_text())
            if not generations:
                unsupported_changes.append(" ".join(text.split()))
                continue

            parsed = False
            for pattern, handler in rules:
                if pattern in text.lower():
                    change = handler(li, text)
                    if change and isinstance(change, dict):
                        all_changes.append(
                            {"generations": generations, "change": change}
                        )
                        parsed = True
                        break
            if not parsed:
                unsupported_changes.append(" ".join(text.split()))
    except Exception as e:
        if isinstance(e, ScraperError):
            raise
        raise ScraperError(f"Failed to parse scraped data for {pokemon_name}") from e

    # Build and cache the result
    output = {
        "metadata": {
            "name": pokemon_name,
            "source": url,
            "schema_version": SCRAPER_CACHE_VERSION,
        },
        "changes": all_changes,
        "unsupported_changes": unsupported_changes,
    }
    if cache_file_path:
        write_json_atomic(cache_file_path, output)

    logger.info(f"Scraped {len(all_changes)} changes for {pokemon_name}")
    if unsupported_changes:
        logger.warning(
            "Could not translate %s Pokémon DB change(s) for %s",
            len(unsupported_changes),
            pokemon_name,
        )
    return output


def _parse_ability(li: Tag, text: str) -> Optional[Dict[str, Any]]:
    """Extracts ability changes from a list item."""
    ability_tag = li.find("a", href=re.compile("/ability/"))
    if ability_tag:
        result = {"ability": _linked_resource_name(ability_tag)}
        form_name = _extract_form_name(text)
        if form_name:
            result["form"] = form_name
        return result
    return None


def _parse_ability_removal(li: Tag, text: str) -> Optional[Dict[str, Any]]:
    """Extracts ability removals (does not have X ability) from a list item."""
    if "does not have" in text.lower():
        ability_tags = li.find_all("a", href=re.compile("/ability/"))
        if ability_tags:
            abilities_to_remove = [
                _linked_resource_name(tag) for tag in ability_tags
            ]
            if len(abilities_to_remove) == 1:
                result = {"remove_ability": abilities_to_remove[0]}
            else:
                result = {"remove_abilities": abilities_to_remove}
            form_name = _extract_form_name(text)
            if form_name:
                result["form"] = form_name
            return result
    return None


def _parse_types(li: Tag, text: str) -> Optional[Dict[str, Any]]:
    """Extracts type changes from a list item, including form information if present."""
    types = [a.get_text(strip=True).lower() for a in li.find_all("a", class_="itype")]
    if types:
        result: Dict[str, Any] = {"types": types}

        # Check for form information in parentheses
        form_name = _extract_form_name(text)
        if form_name:
            result["form"] = form_name

        return result
    return None


def _parse_simple_stat(stat_name: str):
    """
    Creates a parser function for simple stat changes (e.g., base_experience, capture_rate).

    Args:
        stat_name: The name of the stat to parse

    Returns:
        A function that parses the stat value from HTML
    """

    def handler(li: Tag, text: str) -> Optional[Dict[str, Any]]:
        match = re.search(r"of (\d+)", text)
        if match:
            result: Dict[str, Any] = {stat_name: int(match.group(1))}
            form_name = _extract_form_name(text)
            if form_name:
                result["form"] = form_name
            return result
        return None

    return handler


def _parse_base_stat(stat_name: str):
    """
    Creates a parser function for base stat changes (e.g., HP, Attack, Defense).

    Args:
        stat_name: The name of the stat to parse (e.g., 'hp', 'attack')

    Returns:
        A function that parses the base stat value from HTML
    """

    def handler(li: Tag, text: str) -> Optional[Dict[str, Any]]:
        match = re.search(r"of (\d+)", text)
        if match:
            result: Dict[str, Any] = {
                "stats": {stat_name: int(match.group(1))}
            }
            form_name = _extract_form_name(text)
            if form_name:
                result["form"] = form_name
            return result
        return None

    return handler


def _parse_special_stat(li: Tag, text: str) -> Optional[Dict[str, Any]]:
    """
    Parses the single Special stat used by Generation 1.

    In Generation 1, there was only a "Special" stat which later split into
    Special Attack and Special Defense in Generation 2.
    """
    match = re.search(r"base Special stat of (\d+)", text)
    if match:
        value = int(match.group(1))
        result: Dict[str, Any] = {"stats": {"special": value}}
        form_name = _extract_form_name(text)
        if form_name:
            result["form"] = form_name
        return result
    return None


def _parse_ev_yield(li: Tag, text: str) -> Optional[Dict[str, Any]]:
    """
    Parses EV (Effort Value) yield changes from a list item.

    EV yields determine which stats gain effort points when defeating this Pokémon.
    """
    match = re.search(r"has (\d+) ([\w\s]+) EV", text)
    if match:
        effort = int(match.group(1))
        stat_name_raw = match.group(2).strip().lower()

        # Map readable stat names to internal API names
        stat_name_map = {
            "hp": "hp",
            "attack": "attack",
            "defense": "defense",
            "special attack": "special-attack",
            "special defense": "special-defense",
            "speed": "speed",
        }
        stat = stat_name_map.get(stat_name_raw)
        if stat:
            result: Dict[str, Any] = {
                "ev_yield": [{"effort": effort, "stat": stat}]
            }
            form_name = _extract_form_name(text)
            if form_name:
                result["form"] = form_name
            return result
    return None


def _linked_resource_name(tag: Tag) -> str:
    """Returns the canonical slug from a Pokémon DB resource link."""
    href = str(tag.get("href", ""))
    return href.rstrip("/").rsplit("/", 1)[-1]


def _extract_form_name(text: str) -> Optional[str]:
    """Extracts a form qualifier such as ``(Heat Rotom)`` from change text."""
    form_match = re.search(r"\(([^)]+)\)", text)
    return form_match.group(1).strip() if form_match else None
