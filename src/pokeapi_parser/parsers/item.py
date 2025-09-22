import json
import os
from typing import Any, Dict, List, Optional, Union

import requests

from ..utils import get_english_entry
from .base import BaseParser


class ItemParser(BaseParser):
    """A parser for Pokémon items."""

    def __init__(
        self,
        config: Dict[str, Any],
        session: requests.Session,
        generation_version_groups: Dict[int, List[str]],
        target_gen: int,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        super().__init__(config, session, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Item"
        self.api_endpoint = "item"
        self.output_dir_key = "output_dir_item"

    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, Any], str]]:
        """
        Processes a single item from its API reference.

        Args:
            item_ref (Dict[str, str]): A dictionary containing the name and URL of the item.

        Returns:
            A dictionary with summary data for the item, or an error string, or None to skip.
        """
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

            if self.target_gen is not None and introduction_gen <= self.target_gen:
                # Prepare the cleaned data
                fling_effect_obj = data.get("fling_effect")
                fling_effect_name = fling_effect_obj.get("name") if fling_effect_obj else None
                cleaned_data = {
                    "id": data["id"],
                    "name": data["name"],
                    "source_url": item_ref["url"],
                    "cost": data["cost"],
                    "fling_power": data["fling_power"],
                    "fling_effect": fling_effect_name,
                    "attributes": [attr["name"] for attr in data.get("attributes", [])],
                    "category": data.get("category", {}).get("name"),
                    "effect": get_english_entry(data.get("effect_entries", []), "effect"),
                    "short_effect": get_english_entry(data.get("effect_entries", []), "short_effect"),
                    "flavor_text": get_english_entry(
                        data.get("flavor_text_entries", []), "text", self.generation_version_groups, self.target_gen
                    ),
                    "sprite": data.get("sprites", {}).get("default"),
                    "held_by_pokemon": [p["pokemon"]["name"] for p in data.get("held_by_pokemon", [])],
                    "generations": sorted(list(set(gi["generation"]["name"] for gi in game_indices))),
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
