import json
import os
import sys
from typing import Any, Dict, List, Optional

from .api_client import ApiClient


def load_config() -> Dict[str, Any]:
    """Loads settings from the root config.json file."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    with open(config_path, "r") as f:
        return json.load(f)


def get_latest_generation(api_client: ApiClient, config: Dict[str, Any]) -> int:
    """Finds the latest Pokémon generation number by querying the API."""
    print("Determining the latest Pokémon generation...")
    try:
        data = api_client.get(f"{config['api_base_url']}generation/")
        generations = data.get("results", [])
        if not generations:
            raise ValueError("No generations found in API response.")
        latest_gen_num = max(int(g["url"].split("/")[-2]) for g in generations)
        print(f"Latest generation found: {latest_gen_num}")
        return latest_gen_num
    except Exception as e:
        print(f"Fatal: Could not determine latest generation. Error: {e}")
        sys.exit(1)


def get_generation_dex_map(api_client: ApiClient, config: Dict[str, Any]) -> Dict[int, str]:
    """Fetches all Pokédexes and creates a map of generation number to regional dex name."""
    print("Fetching Pokédex information...")
    dex_map: Dict[int, str] = {}
    try:
        pokedex_list = api_client.get(f"{config['api_base_url']}pokedex?limit=100").get("results", [])
        if not pokedex_list:
            raise ValueError("No pokedexes found in API response.")
        for pokedex_ref in pokedex_list:
            dex_data = api_client.get(pokedex_ref["url"])
            if dex_data.get("is_main_series") and dex_data.get("version_groups"):
                vg_data = api_client.get(dex_data["version_groups"][0]["url"])
                gen_num = int(vg_data["generation"]["url"].split("/")[-2])
                if gen_num not in dex_map:
                    dex_map[gen_num] = dex_data["name"]
        print("Successfully created Pokédex map.")
        return dex_map
    except Exception as e:
        print(f"Fatal: Could not create Pokédex map. Error: {e}")
        sys.exit(1)


def get_all_english_entries_for_gen_by_game(
    entries: List[Dict[str, Any]],
    key_name: str,
    generation_version_groups: Optional[Dict[int, List[str]]] = None,
    target_gen: Optional[int] = None,
) -> Dict[str, str]:
    """
    Finds and cleans all unique English entries for a specific generation,
    mapping them to their version group.
    """
    if not entries or not generation_version_groups or target_gen is None:
        return {}

    target_version_groups = generation_version_groups.get(target_gen, [])
    if not target_version_groups:
        return {}

    texts: Dict[str, str] = {}
    for entry in entries:
        version_group_name = entry.get("version_group", {}).get("name")
        if entry.get("language", {}).get("name") == "en" and version_group_name in target_version_groups:
            cleaned_text = " ".join(entry.get(key_name, "").split())
            if cleaned_text and version_group_name not in texts:
                texts[version_group_name] = cleaned_text

    return texts


def get_english_entry(
    entries: List[Dict[str, Any]],
    key_name: str,
    generation_version_groups: Optional[Dict[int, List[str]]] = None,
    target_gen: Optional[int] = None,
) -> Optional[str]:
    """Finds and cleans the English entry from a list of multilingual API entries."""
    if not entries:
        return None

    if entries and "version_group" in entries[0] and generation_version_groups and target_gen:
        all_version_groups: List[str] = []
        for gen in range(target_gen, 0, -1):
            all_version_groups.extend(reversed(generation_version_groups.get(gen, [])))

        entry_map: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            if entry.get("language", {}).get("name") == "en":
                version_group_name = entry.get("version_group", {}).get("name")
                if version_group_name:
                    entry_map[version_group_name] = entry

        for vg_name in all_version_groups:
            if vg_name in entry_map:
                return " ".join(entry_map[vg_name][key_name].split())

    for entry in entries:
        if entry.get("language", {}).get("name") == "en":
            return " ".join(entry[key_name].split())

    return None
