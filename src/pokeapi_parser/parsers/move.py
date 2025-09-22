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
        self.machine_cache = {}

    def _get_machine_for_generation(self, machine_entries):
        """Finds the machine name for the target generation, if it exists."""
        target_version_groups = self.generation_version_groups.get(self.target_gen, [])
        for machine_entry in machine_entries:
            if machine_entry["version_group"]["name"] in target_version_groups:
                machine_url = machine_entry["machine"]["url"]
                if machine_url in self.machine_cache:
                    return self.machine_cache[machine_url]

                try:
                    machine_res = self.session.get(machine_url, timeout=self.config["timeout"])
                    machine_res.raise_for_status()
                    machine_data = machine_res.json()
                    machine_name = machine_data["item"]["name"]
                    self.machine_cache[machine_url] = machine_name
                    return machine_name
                except requests.exceptions.RequestException as e:
                    print(f"Warning: Could not fetch machine data from {machine_url}. Error: {e}")
                    return None
        return None

    def _clean_metadata(self, metadata):
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
        except requests.exceptions.RequestException as e:
            return f"Request failed for {item_ref['name']}: {e}"
        except (KeyError, TypeError) as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
