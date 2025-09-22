import json
import os

import requests

from ..utils import get_english_entry
from .base import BaseParser


class AbilityParser(BaseParser):
    """A parser for Pokémon abilities."""

    def __init__(self, config, session, generation_version_groups, target_gen):
        super().__init__(config, session, generation_version_groups, target_gen)
        self.item_name = "Ability"
        self.api_endpoint = "ability"
        self.output_dir_key = "output_dir_ability"

    def process(self, item_ref):
        """Processes a single ability from its API reference."""
        try:
            response = self.session.get(item_ref["url"], timeout=self.config["timeout"])
            response.raise_for_status()
            data = response.json()

            cleaned_data = {
                "id": data["id"],
                "name": data["name"],
                "source_url": item_ref["url"],
                "is_main_series": data["is_main_series"],
                "generation": data.get("generation", {}).get("name"),
                "effect": get_english_entry(data.get("effect_entries", []), "effect"),
                "short_effect": get_english_entry(data.get("effect_entries", []), "short_effect"),
                "flavor_text": get_english_entry(
                    data.get("flavor_text_entries", []), "flavor_text", self.generation_version_groups, self.target_gen
                ),
                "pokemon": [
                    {"name": p["pokemon"]["name"], "is_hidden": p["is_hidden"], "slot": p["slot"]}
                    for p in data.get("pokemon", [])
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
                "short_effect": cleaned_data["short_effect"],
            }
        except requests.exceptions.RequestException as e:
            return f"Request failed for {item_ref['name']}: {e}"
        except (KeyError, TypeError) as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
