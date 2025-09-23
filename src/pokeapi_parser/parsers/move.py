import json
import os
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..utils import get_english_entry
from .generation import GenerationParser


class MoveParser(GenerationParser):
    """A parser for Pokémon moves."""

    def __init__(
        self,
        config: Dict[str, Any],
        api_client: ApiClient,
        generation_version_groups: Dict[int, List[str]],
        target_gen: int,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        super().__init__(config, api_client, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Move"
        self.api_endpoint = "moves"
        self.output_dir_key = "output_dir_move"

    def _get_machine_for_generation(self, machine_entries: List[Dict[str, Any]]) -> Optional[str]:
        """Finds the machine name for the target generation, if it exists."""
        if not self.generation_version_groups or self.target_gen is None:
            return None
        target_version_groups = self.generation_version_groups.get(self.target_gen, [])
        for machine_entry in machine_entries:
            if machine_entry["version_group"]["name"] in target_version_groups:
                try:
                    machine_data = self.api_client.get(machine_entry["machine"]["url"])
                    return machine_data["item"]["name"]
                except Exception as e:
                    print(f"Warning: Could not fetch machine data from {machine_entry['machine']['url']}. Error: {e}")
                    return None
        return None

    def _clean_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Cleans the metadata object from the API."""
        if not metadata:
            return {}
        ailment = metadata.get("ailment")
        category = metadata.get("category")
        return {
            "ailment": ailment.get("name") if ailment else None,
            "category": category.get("name") if category else None,
            "min_hits": metadata.get("min_hits"),
            "max_hits": metadata.get("max_hits"),
            "min_turns": metadata.get("min_turns"),
            "max_turns": metadata.get("max_turns"),
            "drain": metadata.get("drain"),
            "healing": metadata.get("healing"),
            "crit_rate": metadata.get("crit_rate"),
            "ailment_chance": metadata.get("ailment_chance"),
            "flinch_chance": metadata.get("flinch_chance"),
            "stat_chance": metadata.get("stat_chance"),
        }

    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, Any], str]]:
        """Processes a single move from its API reference."""
        try:
            data = self.api_client.get(item_ref["url"])
            cleaned_data = {
                "id": data["id"],
                "name": data["name"],
                "source_url": item_ref["url"],
                "accuracy": data.get("accuracy"),
                "power": data.get("power"),
                "pp": data.get("pp"),
                "priority": data.get("priority"),
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
                "machine": self._get_machine_for_generation(data.get("machines", [])),
                "metadata": self._clean_metadata(data.get("meta")),
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
        except Exception as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
