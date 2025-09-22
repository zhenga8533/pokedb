import json
import os

import requests
from requests.adapters import HTTPAdapter, Retry


def load_config():
    """Loads settings from the root config.json file."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    with open(config_path, "r") as f:
        return json.load(f)


def setup_session(config):
    """Creates a requests Session with automatic retry logic."""
    session = requests.Session()
    retries = Retry(total=config["max_retries"], backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def get_latest_generation(session, config):
    """Finds the latest Pokémon generation number by querying the API."""
    print("Determining the latest Pokémon generation...")
    try:
        response = session.get(f"{config['api_base_url']}generation/", timeout=config["timeout"])
        response.raise_for_status()
        generations = response.json()["results"]
        latest_gen_num = max(int(g["url"].split("/")[-2]) for g in generations)
        print(f"Latest generation found: {latest_gen_num}")
        return latest_gen_num
    except Exception as e:
        print(f"Could not determine latest generation. Defaulting to 9. Error: {e}")
        return 9  # Fallback to a sensible default


def get_generation_dex_map(session, config):
    """Fetches all Pokédexes and creates a map of generation number to regional dex name."""
    print("Fetching Pokédex information...")
    dex_map = {}
    try:
        # The pokedex endpoint is not paginated, but we set a high limit to be safe
        response = session.get(f"{config['api_base_url']}pokedex?limit=100", timeout=config["timeout"])
        response.raise_for_status()
        pokedexes = response.json()["results"]
        for pokedex_ref in pokedexes:
            # We need to fetch the individual pokedex to find its generation
            dex_res = session.get(pokedex_ref["url"], timeout=config["timeout"])
            dex_res.raise_for_status()
            dex_data = dex_res.json()
            if dex_data.get("is_main_series") and "version_groups" in dex_data and dex_data["version_groups"]:
                # Fetch the version group to find the generation
                vg_res = session.get(dex_data["version_groups"][0]["url"], timeout=config["timeout"])
                vg_res.raise_for_status()
                vg_data = vg_res.json()
                gen_num = int(vg_data["generation"]["url"].split("/")[-2])
                if gen_num not in dex_map:  # Only take the first main series dex we find for a gen
                    dex_map[gen_num] = dex_data["name"]
        print("Successfully created Pokédex map.")
        return dex_map
    except Exception as e:
        print(f"Could not create Pokédex map. Falling back to manual mapping. Error: {e}")
        exit(1)


def get_english_entry(entries, key_name, generation_version_groups=None, target_gen=None):
    """
    Finds and cleans the English entry from a list of multilingual API entries.
    It prioritizes the latest game version within the target generation.
    If not found, it searches backwards from the latest known game version.
    """
    if not entries:
        return None

    # This logic applies to any key that has version_group specific entries.
    if entries and "version_group" in entries[0] and generation_version_groups and target_gen:
        # Create a master list of all version groups from latest to oldest
        all_version_groups = []
        for gen in range(target_gen, 0, -1):
            # The API for generation provides version groups in oldest-to-newest order
            # so we reverse it to prioritize newer games within the same generation.
            all_version_groups.extend(reversed(generation_version_groups.get(gen, [])))

        # Create a quick lookup for entries by version_group name
        entry_map = {}
        for entry in entries:
            if entry.get("language", {}).get("name") == "en":
                version_group_name = entry.get("version_group", {}).get("name")
                if version_group_name:
                    entry_map[version_group_name] = entry

        # Find the best match from our prioritized list
        for vg_name in all_version_groups:
            if vg_name in entry_map:
                return " ".join(entry_map[vg_name][key_name].split())

    # Fallback for entries that are not version-specific or if the above logic fails
    for entry in entries:
        if entry.get("language", {}).get("name") == "en":
            return " ".join(entry[key_name].split())

    return None
