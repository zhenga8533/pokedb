import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup, Tag

from .utils import parse_gen_range


def scrape_pokemon_changes(pokemon_name: str, target_gen: int) -> Dict[str, Any]:
    """
    Scrapes Pokémon DB for historical changes for a specific Pokémon and
    returns a dictionary of changes applicable to the target generation.gs
    """
    changes: Dict[str, Any] = {}
    url = f"https://pokemondb.net/pokedex/{pokemon_name.lower()}"
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")
            break  # If successful, exit the retry loop
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print(
                    f"Warning: Failed to scrape Pokémon DB for {pokemon_name} after {max_retries} attempts. Error: {e}"
                )
                return {}  # Return empty if all retries fail
    else:
        return {}  # Should not be reached, but for safety

    try:
        changes_header = soup.find("h2", string=re.compile(f"{pokemon_name.capitalize()} changes"))
        if not changes_header:
            return {}

        changes_list = changes_header.find_next_sibling("ul")
        if not isinstance(changes_list, Tag):
            return {}

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
            if not generations or target_gen not in generations:
                continue

            found_change = False
            for pattern, handler in rules:
                if pattern in text:
                    change = handler(li, text)
                    if change:
                        if isinstance(change, dict):
                            for key, value in change.items():
                                if isinstance(value, (dict, list)):
                                    if key in changes and isinstance(changes[key], type(value)):
                                        if isinstance(value, dict):
                                            changes[key].update(value)
                                        else:
                                            changes[key].extend(value)
                                    else:
                                        changes[key] = value
                                else:
                                    changes[key] = value
                        found_change = True
                        break
            if not found_change:
                print(f"Warning: Unhandled change for {pokemon_name}: {text}")
    except Exception as e:
        print(f"Warning: Failed to parse scraped data for {pokemon_name}. Error: {e}")

    return changes


def _parse_ability(li: Tag, text: str) -> Optional[Dict[str, str]]:
    ability_tag = li.find("a", href=re.compile("/ability/"))
    if ability_tag:
        return {"ability": ability_tag.get_text(strip=True).lower()}
    return None


def _parse_types(li: Tag, text: str) -> Optional[Dict[str, List[str]]]:
    types = [a.get_text(strip=True).lower() for a in li.find_all("a", class_="itype")]
    if types:
        return {"types": types}
    return None


def _parse_simple_stat(stat_name: str):
    def handler(li: Tag, text: str) -> Optional[Dict[str, int]]:
        match = re.search(r"of (\d+)", text)
        if match:
            return {stat_name: int(match.group(1))}
        return None

    return handler


def _parse_base_stat(stat_name: str):
    def handler(li: Tag, text: str) -> Optional[Dict[str, Dict[str, int]]]:
        match = re.search(r"of (\d+)", text)
        if match:
            return {"stats": {stat_name: int(match.group(1))}}
        return None

    return handler


def _parse_special_stat(li: Tag, text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"base Special stat of (\d+)", text)
    if match:
        value = int(match.group(1))
        return {"stats": {"special-attack": value, "special-defense": value}}
    return None


def _parse_ev_yield(li: Tag, text: str) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    """Parses EV yield changes, which can be complex."""
    match = re.search(r"has (\d+) ([\w\s]+) EV", text)
    if match:
        effort = int(match.group(1))
        stat_name_raw = match.group(2).strip().lower()
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
