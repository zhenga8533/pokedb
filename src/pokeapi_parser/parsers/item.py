import json
import os

import requests

from ..utils import get_english_entry, load_config, run_parser, setup_session


def process_item(item_ref, session, config):
    """Fetches, processes, and structures data for a single item."""
    try:
        response = session.get(item_ref["url"], timeout=config["timeout"])
        response.raise_for_status()
        item_data = response.json()

        fling_effect_obj = item_data.get("fling_effect")
        fling_effect_name = fling_effect_obj.get("name") if fling_effect_obj else None

        cleaned_data = {
            "id": item_data["id"],
            "name": item_data["name"],
            "cost": item_data["cost"],
            "fling_power": item_data["fling_power"],
            "fling_effect": fling_effect_name,
            "attributes": [attr["name"] for attr in item_data.get("attributes", [])],
            "category": item_data.get("category", {}).get("name"),
            "effect": get_english_entry(item_data.get("effect_entries", []), "effect"),
            "flavor_text": get_english_entry(item_data.get("flavor_text_entries", []), "text"),
            "sprite": item_data.get("sprites", {}).get("default"),
            "held_by_pokemon": [p["pokemon"]["name"] for p in item_data.get("held_by_pokemon", [])],
        }

        output_path = config["output_dir_item"]
        os.makedirs(output_path, exist_ok=True)
        file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

        return None
    except requests.exceptions.RequestException as e:
        return f"Request failed for {item_ref['name']}: {e}"
    except (KeyError, TypeError) as e:
        return f"Parsing failed for {item_ref['name']}: {e}"


def main(config, session):
    """Orchestrates the item parsing process."""
    print("Starting the Item Parser...")

    parser_config = {
        "item_name": "Item",
        "master_list_url": f"{config['api_base_url']}item?limit=2500",
        "processing_func": process_item,
        "session": session,
        "config": config,
    }

    run_parser(parser_config)


if __name__ == "__main__":
    config = load_config()
    session = setup_session(config)
    main(config, session)
