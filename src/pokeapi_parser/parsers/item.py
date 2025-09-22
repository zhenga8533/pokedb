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
        self.target_gen = 0

    def process_item_for_target_gen(self, item_ref):
        """Processes a single item and saves it ONLY to the target generation folder."""
        try:
            response = self.session.get(item_ref["url"], timeout=self.config["timeout"])
            response.raise_for_status()
            data = response.json()

            # Find the first generation this item appeared in
            game_indices = data.get("game_indices", [])
            if not game_indices:
                return None  # Skip items with no generation data

            intro_gen_str = min(gi["generation"]["url"].split("/")[-2] for gi in game_indices)
            introduction_gen = int(intro_gen_str)

            # --- MODIFIED: Only proceed if the item is from the correct generation ---
            if introduction_gen <= self.target_gen:
                # Prepare the cleaned data
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

                # Save the data to the single target generation folder
                output_path = self.config[self.output_dir_key]
                os.makedirs(output_path, exist_ok=True)
                file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

                return {"name": cleaned_data["name"], "id": cleaned_data["id"], "sprite": cleaned_data["sprite"]}

            return None
        except requests.exceptions.RequestException as e:
            return f"Request failed for {item_ref['name']}: {e}"
        except (ValueError, KeyError, TypeError) as e:
            return f"Processing failed for {item_ref['name']}: {e}"

    # Override the process method to call the new one
    def process(self, item_ref):
        return self.process_item_for_target_gen(item_ref)

    # Override the run method to set the target generation
    def run(self, all_items):
        try:
            # Determine target generation from the formatted path in the config
            self.target_gen = int(self.config[self.output_dir_key].split("/gen")[1].split("/")[0])
        except (IndexError, ValueError):
            print("Warning: Could not determine target generation for ItemParser. Aborting item processing.")
            return

        # Call the original run method from the BaseParser
        super().run(all_items)
