import json
import os

import requests

from ..utils import get_english_entry, load_config, run_parser, setup_session


def process_ability(ability_ref, session, config):
    """Fetches, processes, and structures data for a single ability."""
    try:
        response = session.get(ability_ref["url"], timeout=config["timeout"])
        response.raise_for_status()
        ability_data = response.json()

        cleaned_data = {
            "id": ability_data["id"],
            "name": ability_data["name"],
            "is_main_series": ability_data["is_main_series"],
            "generation": ability_data.get("generation", {}).get("name"),
            "effect": get_english_entry(ability_data.get("effect_entries", []), "effect"),
            "short_effect": get_english_entry(ability_data.get("effect_entries", []), "short_effect"),
            "flavor_text": get_english_entry(ability_data.get("flavor_text_entries", []), "flavor_text"),
            "pokemon": [
                {
                    "name": p["pokemon"]["name"],
                    "is_hidden": p["is_hidden"],
                    "slot": p["slot"],
                }
                for p in ability_data.get("pokemon", [])
            ],
        }

        output_path = config["output_dir_ability"]
        os.makedirs(output_path, exist_ok=True)
        file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

        return None
    except requests.exceptions.RequestException as e:
        return f"Request failed for {ability_ref['name']}: {e}"
    except (KeyError, TypeError) as e:
        return f"Parsing failed for {ability_ref['name']}: {e}"


def main():
    """Orchestrates the ability parsing process."""
    print("Starting the Ability Parser...")
    config = load_config()
    session = setup_session(config)

    parser_config = {
        "item_name": "Ability",
        "master_list_url": f"{config['api_base_url']}ability?limit=1000",
        "processing_func": process_ability,
        "session": session,
        "config": config,
    }

    run_parser(parser_config)


if __name__ == "__main__":
    main()
