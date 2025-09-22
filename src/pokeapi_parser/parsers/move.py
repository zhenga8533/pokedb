import json
import os

import requests

from ..utils import get_english_entry, load_config, run_parser, setup_session


def process_move(move_ref, session, config):
    """Fetches, processes, and structures data for a single move."""
    try:
        response = session.get(move_ref["url"], timeout=config["timeout"])
        response.raise_for_status()
        move_data = response.json()

        cleaned_data = {
            "id": move_data["id"],
            "name": move_data["name"],
            "accuracy": move_data.get("accuracy"),
            "power": move_data.get("power"),
            "pp": move_data["pp"],
            "priority": move_data["priority"],
            "damage_class": move_data.get("damage_class", {}).get("name"),
            "type": move_data.get("type", {}).get("name"),
            "target": move_data.get("target", {}).get("name"),
            "generation": move_data.get("generation", {}).get("name"),
            "effect_chance": move_data.get("effect_chance"),
            "effect": get_english_entry(move_data.get("effect_entries", []), "effect"),
            "short_effect": get_english_entry(move_data.get("effect_entries", []), "short_effect"),
            "flavor_text": get_english_entry(move_data.get("flavor_text_entries", []), "flavor_text"),
            "learned_by_pokemon": [p["name"] for p in move_data.get("learned_by_pokemon", [])],
            "stat_changes": [
                {"change": sc["change"], "stat": sc.get("stat", {}).get("name")}
                for sc in move_data.get("stat_changes", [])
            ],
        }

        output_path = config["output_dir_move"]
        os.makedirs(output_path, exist_ok=True)
        file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

        return None
    except requests.exceptions.RequestException as e:
        return f"Request failed for {move_ref['name']}: {e}"
    except (KeyError, TypeError) as e:
        return f"Parsing failed for {move_ref['name']}: {e}"


def main():
    """Orchestrates the move parsing process."""
    print("Starting the Move Parser...")
    config = load_config()
    session = setup_session(config)

    parser_config = {
        "item_name": "Move",
        "master_list_url": f"{config['api_base_url']}move?limit=1000",
        "processing_func": process_move,
        "session": session,
        "config": config,
    }

    run_parser(parser_config)


if __name__ == "__main__":
    main()
