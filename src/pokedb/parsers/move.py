import json
import os
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..utils import get_all_english_entries_for_gen_by_game, get_english_entry, transform_keys_to_snake_case
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

    def _apply_past_values(self, cleaned_data: Dict[str, Any], past_values: List[Dict[str, Any]]):
        """Applies historical values to the data if applicable for the target generation."""
        if not self.target_gen or not self.generation_version_groups:
            return

        vg_to_gen_map = {
            vg_name: gen_num for gen_num, vg_list in self.generation_version_groups.items() for vg_name in vg_list
        }

        target_gen_vgs = self.generation_version_groups.get(self.target_gen, [])
        change_fields = ["accuracy", "power", "pp", "effect_chance", "type", "effect", "short_effect"]
        gen_specific_values: Dict[str, Dict[str, Any]] = {field: {} for field in change_fields}

        for vg_name in target_gen_vgs:
            temp_data = {
                "accuracy": cleaned_data.get("accuracy"),
                "power": cleaned_data.get("power"),
                "pp": cleaned_data.get("pp"),
                "effect_chance": cleaned_data.get("effect_chance"),
                "type": cleaned_data.get("type"),
                "effect": cleaned_data.get("effect"),
                "short_effect": cleaned_data.get("short_effect"),
            }
            sorted_past_values = sorted(
                [pv for pv in past_values if vg_to_gen_map.get(pv["version_group"]["name"], 999) <= self.target_gen],
                key=lambda x: vg_to_gen_map.get(x["version_group"]["name"], 999),
            )
            for pv in sorted_past_values:
                if vg_to_gen_map.get(pv["version_group"]["name"], 999) > vg_to_gen_map.get(vg_name, 0):
                    break
                if pv.get("accuracy") is not None:
                    temp_data["accuracy"] = pv["accuracy"]
                if pv.get("power") is not None:
                    temp_data["power"] = pv["power"]
                if pv.get("pp") is not None:
                    temp_data["pp"] = pv["pp"]
                if pv.get("effect_chance") is not None:
                    temp_data["effect_chance"] = pv["effect_chance"]
                if pv.get("type"):
                    temp_data["type"] = pv["type"]["name"]
                if pv.get("effect_entries"):
                    effect = get_english_entry(pv["effect_entries"], "effect")
                    short_effect = get_english_entry(pv["effect_entries"], "short_effect")
                    if effect:
                        temp_data["effect"] = effect
                    if short_effect:
                        temp_data["short_effect"] = short_effect

            for field in change_fields:
                gen_specific_values[field][vg_name] = temp_data[field]

        for field, values_map in gen_specific_values.items():
            cleaned_data[field] = values_map

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
                "flavor_text": get_all_english_entries_for_gen_by_game(
                    data.get("flavor_text_entries", []), "flavor_text", self.generation_version_groups, self.target_gen
                ),
                "stat_changes": [
                    {"change": sc["change"], "stat": sc.get("stat", {}).get("name")}
                    for sc in data.get("stat_changes", [])
                ],
                "machine": self._get_machine_for_generation(data.get("machines", [])),
                "metadata": self._clean_metadata(data.get("meta")),
            }

            past_values = data.get("past_values", [])
            if past_values:
                self._apply_past_values(cleaned_data, past_values)

            output_path = self.config[self.output_dir_key]
            os.makedirs(output_path, exist_ok=True)
            file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(transform_keys_to_snake_case(cleaned_data), f, indent=4, ensure_ascii=False)

            return {"name": cleaned_data["name"], "id": cleaned_data["id"]}
        except Exception as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
