import json
import os
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..utils import get_english_entry
from .base import BaseParser


class ItemParser(BaseParser):
    """A parser for Pokémon items."""

    def __init__(
        self,
        config: Dict[str, Any],
        api_client: ApiClient,
        generation_version_groups: Dict[int, List[str]],
        target_gen: int,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        super().__init__(config, api_client, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Item"
        self.api_endpoint = "item"
        self.output_dir_key = "output_dir_item"

    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, Any], str]]:
        """Processes a single item from its API reference."""
        try:
            data = self.api_client.get(item_ref["url"])
            game_indices = data.get("game_indices", [])
            if not game_indices:
                return None

            introduction_gen = int(min(gi["generation"]["url"].split("/")[-2] for gi in game_indices))

            if self.target_gen is not None and introduction_gen <= self.target_gen:
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

                output_path = self.config[self.output_dir_key]
                os.makedirs(output_path, exist_ok=True)
                file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

                return {"name": cleaned_data["name"], "id": cleaned_data["id"], "sprite": cleaned_data["sprite"]}
            return None
        except Exception as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
