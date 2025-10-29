import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag

from .utils import get_cache_path, load_config, parse_gen_range

logger = logging.getLogger(__name__)

# Constants
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 10


def scrape_pokemon_changes(pokemon_name: str) -> Dict[str, Any]:
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
    config = load_config()
    cache_dir = config.get("scraper_cache_dir")
    cache_expires = config.get("cache_expires")

    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

    url = f"https://pokemondb.net/pokedex/{pokemon_name.lower()}"
    cache_file_path: Optional[Path] = None

    # Check cache
    if cache_dir and cache_expires is not None:
        cache_file_path = get_cache_path(url, cache_dir)
        if cache_file_path.exists():
            file_mod_time = cache_file_path.stat().st_mtime
            if time.time() - file_mod_time < cache_expires:
                logger.debug(f"Cache hit for {pokemon_name}")
                with open(cache_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)

    # Fetch HTML from PokemonDB
    all_changes: List[Dict[str, Any]] = []
    soup: Optional[BeautifulSoup] = None

    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(
                f"Scraping {pokemon_name} (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")
            break
        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(
                    f"Scraping attempt {attempt + 1} failed for {pokemon_name}, retrying..."
                )
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(
                    f"Failed to scrape {url} after {MAX_RETRIES} attempts: {e}"
                )
                return {}

    if not soup:
        return {}

    # Parse the changes section
    try:
        changes_header = next(
            (
                h
                for h in soup.find_all("h2")
                if isinstance(h, Tag)
                and re.search(f"{pokemon_name.capitalize()} changes", h.get_text())
            ),
            None,
        )
        if not changes_header:
            logger.debug(f"No changes section found for {pokemon_name}")
            empty_result = {
                "metadata": {"name": pokemon_name, "source": url},
                "changes": [],
            }
            if cache_file_path:
                with open(cache_file_path, "w", encoding="utf-8") as f:
                    json.dump(empty_result, f, indent=4, ensure_ascii=False)
            return empty_result

        changes_list = changes_header.find_next_sibling("ul")
        if not isinstance(changes_list, Tag):
            empty_result = {
                "metadata": {"name": pokemon_name, "source": url},
                "changes": [],
            }
            if cache_file_path:
                with open(cache_file_path, "w", encoding="utf-8") as f:
                    json.dump(empty_result, f, indent=4, ensure_ascii=False)
            return empty_result

        rules = [
            ("ability", _parse_ability),
            ("type", _parse_types),
            ("base experience yield", _parse_simple_stat("base_experience")),
            ("base Friendship value", _parse_simple_stat("base_happiness")),
            ("catch rate", _parse_simple_stat("capture_rate")),
            ("EVs", _parse_ev_yield),
            ("base Special stat", _parse_special_stat),
            ("base HP", _parse_base_stat("hp")),
            ("base Attack", _parse_base_stat("attack")),
            ("base Defense", _parse_base_stat("defense")),
            ("base Special Attack", _parse_base_stat("special-attack")),
            ("base Special Defense", _parse_base_stat("special-defense")),
            ("base Speed", _parse_base_stat("speed")),
        ]

        for li in changes_list.find_all("li"):
            if not isinstance(li, Tag):
                continue

            text = li.get_text()
            gen_abbr = li.find("abbr")
            if not gen_abbr:
                continue

            generations = parse_gen_range(gen_abbr.get_text())
            if not generations:
                continue

            for pattern, handler in rules:
                if pattern in text:
                    change = handler(li, text)
                    if change and isinstance(change, dict):
                        all_changes.append(
                            {"generations": generations, "change": change}
                        )
                        break
    except Exception as e:
        logger.warning(f"Failed to parse scraped data for {pokemon_name}: {e}")

    # Build and cache the result
    output = {"metadata": {"name": pokemon_name, "source": url}, "changes": all_changes}
    if cache_file_path:
        with open(cache_file_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)

    logger.info(f"Scraped {len(all_changes)} changes for {pokemon_name}")
    return output


def _parse_ability(li: Tag, text: str) -> Optional[Dict[str, str]]:
    """Extracts ability changes from a list item."""
    ability_tag = li.find("a", href=re.compile("/ability/"))
    if ability_tag:
        return {"ability": ability_tag.get_text(strip=True).lower()}
    return None


def _parse_types(li: Tag, text: str) -> Optional[Dict[str, List[str]]]:
    """Extracts type changes from a list item."""
    types = [a.get_text(strip=True).lower() for a in li.find_all("a", class_="itype")]
    if types:
        return {"types": types}
    return None


def _parse_simple_stat(stat_name: str):
    """
    Creates a parser function for simple stat changes (e.g., base_experience, capture_rate).

    Args:
        stat_name: The name of the stat to parse

    Returns:
        A function that parses the stat value from HTML
    """

    def handler(li: Tag, text: str) -> Optional[Dict[str, int]]:
        match = re.search(r"of (\d+)", text)
        if match:
            return {stat_name: int(match.group(1))}
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

    def handler(li: Tag, text: str) -> Optional[Dict[str, Dict[str, int]]]:
        match = re.search(r"of (\d+)", text)
        if match:
            return {"stats": {stat_name: int(match.group(1))}}
        return None

    return handler


def _parse_special_stat(li: Tag, text: str) -> Optional[Dict[str, Any]]:
    """
    Parses Gen 1 Special stat changes (affects both Special Attack and Special Defense).

    In Generation 1, there was only a "Special" stat which later split into
    Special Attack and Special Defense in Generation 2.
    """
    match = re.search(r"base Special stat of (\d+)", text)
    if match:
        value = int(match.group(1))
        return {"stats": {"special-attack": value, "special-defense": value}}
    return None


def _parse_ev_yield(li: Tag, text: str) -> Optional[Dict[str, List[Dict[str, Any]]]]:
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
            return {"ev_yield": [{"effort": effort, "stat": stat}]}
    return None
