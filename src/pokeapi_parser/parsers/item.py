import json
import os

import requests

from ..utils import get_english_entry
from .base import BaseParser


class ItemParser(BaseParser):
    """A parser for Pokémon items."""

    def __init__(self, config, session):
        super().__init__(config, session)
        self.item_name = "Item"
        self.api_endpoint = "item"
        self.output_dir_key = "output_dir_item"

    def process(self, item_ref):
        """Processes a single item from its API reference."""
        try:
            response = self.session.get(item_ref["url"], timeout=self.config["timeout"])
            response.raise_for_status()
            data = response.json()

            fling_effect_obj = data.get("fling_effect")
            fling_effect_name = fling_effect_obj.get("name") if fling_effect_obj else None

            cleaned_data = {
                "id": data["id"],
                "name": data["name"],
                "cost": data["cost"],
                "fling_power": data["fling_power"],
                "fling_effect": fling_effect_name,
                "attributes": [attr["name"] for attr in data.get("attributes", [])],
                "category": data.get("category", {}).get("name"),
                "effect": get_english_entry(data.get("effect_entries", []), "effect"),
                "flavor_text": get_english_entry(data.get("flavor_text_entries", []), "text"),
                "sprite": data.get("sprites", {}).get("default"),
                "held_by_pokemon": [p["pokemon"]["name"] for p in data.get("held_by_pokemon", [])],
            }

            output_path = self.config[self.output_dir_key]
            os.makedirs(output_path, exist_ok=True)
            file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
            return None
        except requests.exceptions.RequestException as e:
            return f"Request failed for {item_ref['name']}: {e}"
        except (KeyError, TypeError) as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
