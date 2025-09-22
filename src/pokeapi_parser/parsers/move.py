import json
import os

import requests

from ..utils import get_english_entry
from .base import BaseParser


class MoveParser(BaseParser):
    """A parser for Pokémon moves."""

    def __init__(self, config, session, generation_version_groups, target_gen):
        super().__init__(config, session, generation_version_groups, target_gen)
        self.item_name = "Move"
        self.api_endpoint = "move"
        self.output_dir_key = "output_dir_move"

    def process(self, item_ref):
        """Processes a single move from its API reference."""
        try:
            response = self.session.get(item_ref["url"], timeout=self.config["timeout"])
            response.raise_for_status()
            data = response.json()

            cleaned_data = {
                "id": data["id"],
                "name": data["name"],
                "source_url": item_ref["url"],
                "accuracy": data.get("accuracy"),
                "power": data.get("power"),
                "pp": data["pp"],
                "priority": data["priority"],
                "damage_class": data.get("damage_class", {}).get("name"),
                "type": data.get("type", {}).get("name"),
                "target": data.get("target", {}).get("name"),
                "generation": data.get("generation", {}).get("name"),
                "effect_chance": data.get("effect_chance"),
                "effect": get_english_entry(data.get("effect_entries", []), "effect"),
                "short_effect": get_english_entry(data.get("effect_entries", []), "short_effect"),
                "flavor_text": get_english_entry(
                    data.get("flavor_text_entries", []), "flavor_text", self.generation_version_groups, self.target_gen
                ),
                "learned_by_pokemon": [p["name"] for p in data.get("learned_by_pokemon", [])],
                "stat_changes": [
                    {"change": sc["change"], "stat": sc.get("stat", {}).get("name")}
                    for sc in data.get("stat_changes", [])
                ],
            }

            output_path = self.config[self.output_dir_key]
            os.makedirs(output_path, exist_ok=True)
            file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

            return {
                "name": cleaned_data["name"],
                "id": cleaned_data["id"],
                "type": cleaned_data["type"],
                "damage_class": cleaned_data["damage_class"],
            }
        except requests.exceptions.RequestException as e:
            return f"Request failed for {item_ref['name']}: {e}"
        except (KeyError, TypeError) as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
