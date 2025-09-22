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


def get_english_entry(entries, key_name, generation_version_groups=None, target_gen=None):
    """Finds and cleans the English entry from a list of multilingual API entries."""
    if not entries:
        return None

    if key_name == "flavor_text" and generation_version_groups and target_gen:
        # Get the version groups for the target generation in reverse order (latest first)
        version_groups = reversed(generation_version_groups.get(target_gen, []))
        for version_group in version_groups:
            for entry in entries:
                if (
                    entry.get("language", {}).get("name") == "en"
                    and entry.get("version_group", {}).get("name") == version_group
                ):
                    return " ".join(entry[key_name].split())

    # Fallback for other keys or if no version-specific entry is found
    for entry in entries:
        if entry.get("language", {}).get("name") == "en":
            return " ".join(entry[key_name].split())

    return None
