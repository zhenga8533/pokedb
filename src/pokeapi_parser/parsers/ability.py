import json
import os
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..utils import get_english_entry
from .base import BaseParser


class AbilityParser(BaseParser):
    """A parser for Pokémon abilities."""

    def __init__(
        self,
        config: Dict[str, Any],
        api_client: ApiClient,
        generation_version_groups: Dict[int, List[str]],
        target_gen: int,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        super().__init__(config, api_client, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Ability"
        self.api_endpoint = "ability"
        self.output_dir_key = "output_dir_ability"

    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, Any], str]]:
        """Processes a single ability from its API reference."""
        try:
            data = self.api_client.get(item_ref["url"])
            cleaned_data = {
                "id": data["id"],
                "name": data["name"],
                "source_url": item_ref["url"],
                "is_main_series": data.get("is_main_series"),
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
        except Exception as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
