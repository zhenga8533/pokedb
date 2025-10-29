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


class AbilityParser(GenerationParser):
    """
    A parser for Pokémon abilities.

    This parser fetches ability data from the PokéAPI, processes it for a specific
    generation, and writes individual JSON files for each ability.

    Features:
    - Handles generation-specific effect changes
    - Extracts flavor text for all version groups in the target generation
    - Processes both current and historical ability effects
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
        self.entity_type = "Ability"
        self.api_endpoint = "abilities"
        self.output_dir_key = "output_dir_ability"

    def process(
        self, resource_ref: Dict[str, str]
    ) -> Optional[Union[Dict[str, Any], str]]:
        """
        Processes a single ability from its API reference.

        This method fetches the full ability data, processes generation-specific
        effect changes, and writes the result to a JSON file.

        Args:
            resource_ref: Dictionary containing 'name' and 'url' for the ability

        Returns:
            A summary dict with name and id, or an error string if processing fails
        """
        try:
            data = self.api_client.get(resource_ref["url"])

            # Build the basic ability data structure
            cleaned_data = {
                "id": data["id"],
                "name": data["name"],
                "source_url": resource_ref["url"],
                "is_main_series": data.get("is_main_series"),
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
            }

            # Process generation-specific effect changes
            effect_changes = data.get("effect_changes", [])
            if self.target_gen and self.generation_version_groups and effect_changes:
                version_group_to_gen_map = build_version_group_to_generation_map(
                    self.generation_version_groups
                )
                target_gen_version_groups = self.generation_version_groups.get(
                    self.target_gen, []
                )
                effect_map = {}

                # short_effect is not tracked in effect_changes, so use the latest version
                latest_short_effect = get_english_entry(
                    data.get("effect_entries", []), "short_effect"
                )

                # Build effect map for each version group in the target generation
                for version_group_name in target_gen_version_groups:
                    current_effect = get_english_entry(
                        data.get("effect_entries", []), "effect"
                    )

                    # Get all effect changes up to and including the target generation, sorted chronologically
                    sorted_effect_changes = sorted(
                        [
                            change
                            for change in effect_changes
                            if version_group_to_gen_map.get(
                                change["version_group"]["name"], 999
                            )
                            <= self.target_gen
                        ],
                        key=lambda x: version_group_to_gen_map.get(
                            x["version_group"]["name"], 999
                        ),
                    )

                    # Apply effect changes up to this version group
                    for change in sorted_effect_changes:
                        change_gen = version_group_to_gen_map.get(
                            change["version_group"]["name"], 999
                        )
                        current_gen = version_group_to_gen_map.get(
                            version_group_name, 0
                        )

                        if change_gen > current_gen:
                            break

                        effect = get_english_entry(
                            change.get("effect_entries", []), "effect"
                        )
                        if effect:
                            current_effect = effect

                    effect_map[version_group_name] = current_effect

                cleaned_data["effect"] = effect_map
                cleaned_data["short_effect"] = latest_short_effect

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
