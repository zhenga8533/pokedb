import json
import os
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..utils import get_all_english_entries_for_gen_by_game, get_english_entry
from .generation import GenerationParser


class AbilityParser(GenerationParser):
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
        self.api_endpoint = "abilities"
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
                "effect": get_english_entry(data.get("effect_entries", []), "effect"),
                "short_effect": get_english_entry(data.get("effect_entries", []), "short_effect"),
                "flavor_text": get_all_english_entries_for_gen_by_game(
                    data.get("flavor_text_entries", []),
                    "flavor_text",
                    self.generation_version_groups,
                    self.target_gen,
                ),
            }

            effect_changes = data.get("effect_changes", [])
            if self.target_gen and self.generation_version_groups:
                vg_to_gen_map = {
                    vg_name: gen_num
                    for gen_num, vg_list in self.generation_version_groups.items()
                    for vg_name in vg_list
                }
                target_gen_vgs = self.generation_version_groups.get(self.target_gen, [])
                effect_map = {}
                short_effect_map = {}

                for vg_name in target_gen_vgs:
                    current_effect = get_english_entry(data.get("effect_entries", []), "effect")
                    current_short_effect = get_english_entry(data.get("effect_entries", []), "short_effect")
                    sorted_effect_changes = sorted(
                        [
                            ec
                            for ec in effect_changes
                            if vg_to_gen_map.get(ec["version_group"]["name"], 999) <= self.target_gen
                        ],
                        key=lambda x: vg_to_gen_map.get(x["version_group"]["name"], 999),
                    )
                    for ec in sorted_effect_changes:
                        if vg_to_gen_map.get(ec["version_group"]["name"], 999) > vg_to_gen_map.get(vg_name, 0):
                            break
                        effect = get_english_entry(ec.get("effect_entries", []), "effect")
                        short_effect = get_english_entry(ec.get("effect_entries", []), "short_effect")
                        if effect:
                            current_effect = effect
                        if short_effect:
                            current_short_effect = short_effect
                    effect_map[vg_name] = current_effect
                    short_effect_map[vg_name] = current_short_effect
                cleaned_data["effect"] = effect_map
                cleaned_data["short_effect"] = short_effect_map

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
