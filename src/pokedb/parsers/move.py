from logging import getLogger
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..utils import (
    build_version_group_to_generation_map,
    get_all_english_entries_for_gen_by_game,
    get_english_entry,
    write_json_file,
)
from .generation import GenerationParser

logger = getLogger(__name__)


class MoveParser(GenerationParser):
    """
    A parser for Pokémon moves.

    This parser fetches move data from the PokéAPI, processes generation-specific
    changes, and writes individual JSON files for each move.

    Features:
    - Handles generation-specific stat changes (power, PP, accuracy, etc.)
    - Processes move metadata (ailments, categories, hit/turn ranges)
    - Tracks TM/HM machine assignments per generation
    - Applies historical values for older generations
    """

    def __init__(
        self,
        config: Dict[str, Any],
        api_client: ApiClient,
        generation_version_groups: Dict[int, List[str]],
        target_gen: int,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        super().__init__(
            config,
            api_client,
            generation_version_groups,
            target_gen,
            generation_dex_map,
        )
        self.entity_type = "Move"
        self.api_endpoint = "moves"
        self.output_dir_key = "output_dir_move"

    def _get_machine_for_generation(
        self, machine_entries: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Finds the TM/HM machine item name for the target generation.

        Args:
            machine_entries: List of machine entry dicts from the move API data

        Returns:
            The machine item name (e.g., 'tm01', 'hm05') or None if not a machine move
        """
        if not self.generation_version_groups or self.target_gen is None:
            return None

        target_version_groups = self.generation_version_groups.get(self.target_gen, [])

        for machine_entry in machine_entries:
            if machine_entry["version_group"]["name"] in target_version_groups:
                try:
                    machine_data = self.api_client.get(machine_entry["machine"]["url"])
                    return machine_data["item"]["name"]
                except Exception as e:
                    logger.warning(
                        f"Could not fetch machine data from {machine_entry['machine']['url']}: {e}"
                    )
                    return None
        return None

    def _clean_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Cleans and normalizes move metadata from the API.

        Move metadata includes information about ailments, hit/turn ranges,
        drain/healing percentages, and various probability chances.

        Args:
            metadata: The 'meta' dictionary from move API data, or None

        Returns:
            A cleaned metadata dictionary with consistent default values
        """
        # Provide default values if metadata is missing
        if not metadata:
            return {
                "ailment": None,
                "category": None,
                "min_hits": None,
                "max_hits": None,
                "min_turns": None,
                "max_turns": None,
                "drain": 0,
                "healing": 0,
                "crit_rate": 0,
                "ailment_chance": 0,
                "flinch_chance": 0,
                "stat_chance": 0,
            }

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

    def _apply_past_values(
        self, cleaned_data: Dict[str, Any], past_values: List[Dict[str, Any]]
    ):
        """
        Applies historical stat changes to move data for the target generation.

        Many moves have had their stats changed across generations (e.g., Gust
        became Flying-type in Gen 2, many moves had power/accuracy adjusted).
        This method creates generation-specific values for each version group.

        Args:
            cleaned_data: The move data dictionary to modify in-place
            past_values: List of past value changes from the API

        Modifies:
            cleaned_data: Converts single values to version-group-specific dicts
        """
        if not self.target_gen or not self.generation_version_groups:
            return

        version_group_to_gen_map = build_version_group_to_generation_map(
            self.generation_version_groups
        )

        target_gen_version_groups = self.generation_version_groups.get(
            self.target_gen, []
        )

        # Fields that can change across generations
        change_fields = [
            "accuracy",
            "power",
            "pp",
            "effect_chance",
            "type",
            "effect",
            "short_effect",
        ]
        generation_specific_values: Dict[str, Dict[str, Any]] = {
            field: {} for field in change_fields
        }

        # For each version group in the target generation
        for version_group_name in target_gen_version_groups:
            # Start with current values
            temp_data = {
                "accuracy": cleaned_data.get("accuracy"),
                "power": cleaned_data.get("power"),
                "pp": cleaned_data.get("pp"),
                "effect_chance": cleaned_data.get("effect_chance"),
                "type": cleaned_data.get("type"),
                "effect": cleaned_data.get("effect"),
                "short_effect": cleaned_data.get("short_effect"),
            }

            # Get all past values up to target generation, sorted chronologically
            sorted_past_values = sorted(
                [
                    past_value
                    for past_value in past_values
                    if version_group_to_gen_map.get(
                        past_value["version_group"]["name"], 999
                    )
                    <= self.target_gen
                ],
                key=lambda x: version_group_to_gen_map.get(
                    x["version_group"]["name"], 999
                ),
            )

            # Apply past values chronologically up to this version group
            for past_value in sorted_past_values:
                past_value_gen = version_group_to_gen_map.get(
                    past_value["version_group"]["name"], 999
                )
                current_version_group_gen = version_group_to_gen_map.get(
                    version_group_name, 0
                )

                # Stop if this change happened after the current version group
                if past_value_gen > current_version_group_gen:
                    break

                # Apply each changed field
                if past_value.get("accuracy") is not None:
                    temp_data["accuracy"] = past_value["accuracy"]
                if past_value.get("power") is not None:
                    temp_data["power"] = past_value["power"]
                if past_value.get("pp") is not None:
                    temp_data["pp"] = past_value["pp"]
                if past_value.get("effect_chance") is not None:
                    temp_data["effect_chance"] = past_value["effect_chance"]
                if past_value.get("type"):
                    temp_data["type"] = past_value["type"]["name"]
                if past_value.get("effect_entries"):
                    effect = get_english_entry(past_value["effect_entries"], "effect")
                    short_effect = get_english_entry(
                        past_value["effect_entries"], "short_effect"
                    )
                    if effect:
                        temp_data["effect"] = effect
                    if short_effect:
                        temp_data["short_effect"] = short_effect

            # Store the final values for this version group
            for field in change_fields:
                generation_specific_values[field][version_group_name] = temp_data[field]

        # Replace single values with version-group-specific dictionaries
        for field, values_map in generation_specific_values.items():
            cleaned_data[field] = values_map

    def process(
        self, resource_ref: Dict[str, str]
    ) -> Optional[Union[Dict[str, Any], str]]:
        """
        Processes a single move from its API reference.

        This method fetches the full move data, processes generation-specific changes,
        and writes the result to a JSON file.

        Args:
            resource_ref: Dictionary containing 'name' and 'url' for the move

        Returns:
            A summary dict with name and id, or an error string if processing fails
        """
        try:
            data = self.api_client.get(resource_ref["url"])

            # Build the basic move data structure
            cleaned_data = {
                "id": data["id"],
                "name": data["name"],
                "source_url": resource_ref["url"],
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
                "short_effect": get_english_entry(
                    data.get("effect_entries", []), "short_effect"
                ),
                "flavor_text": get_all_english_entries_for_gen_by_game(
                    data.get("flavor_text_entries", []),
                    "flavor_text",
                    self.generation_version_groups,
                    self.target_gen,
                ),
                "stat_changes": [
                    {
                        "change": stat_change["change"],
                        "stat": stat_change.get("stat", {}).get("name"),
                    }
                    for stat_change in data.get("stat_changes", [])
                ],
                "machine": self._get_machine_for_generation(data.get("machines", [])),
                "metadata": self._clean_metadata(data.get("meta")),
            }

            # Apply historical stat changes for the target generation
            past_values = data.get("past_values", [])
            self._apply_past_values(cleaned_data, past_values)

            # Write to file
            output_path = self.config[self.output_dir_key]
            write_json_file(output_path, cleaned_data["name"], cleaned_data)

            return {"name": cleaned_data["name"], "id": cleaned_data["id"]}

        except (KeyError, ValueError) as e:
            return f"Parsing failed for {resource_ref.get('name', 'unknown')}: {type(e).__name__} - {e}"
        except Exception as e:
            logger.error(
                f"Unexpected error processing {resource_ref.get('name', 'unknown')}: {e}"
            )
            return f"Parsing failed for {resource_ref.get('name', 'unknown')}: {e}"
