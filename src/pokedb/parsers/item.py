from logging import getLogger
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..utils import (
    DEFAULT_API_LIMIT,
    get_all_english_entries_for_gen_by_game,
    get_english_entry,
    write_json_file,
)
from .base import BaseParser

logger = getLogger(__name__)


class ItemParser(BaseParser):
    """
    A parser for Pokémon items.

    This parser fetches all items from the PokéAPI and filters them based on
    the target generation. It writes individual JSON files for each item that
    exists in the target generation.

    Features:
    - Generation-based filtering using game indices
    - Extracts item attributes, effects, and flavor text
    - Handles fling mechanics (power and effect)
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
        self.entity_type = "Item"
        self.api_endpoint = "item"
        self.output_dir_key = "output_dir_item"

    def _get_all_item_refs(self) -> List[Dict[str, str]]:
        """
        Retrieves all item references from the API.

        Unlike generation-specific parsers, items must be fetched from a single
        endpoint with a high limit, then filtered by generation.

        Returns:
            A list of item reference dictionaries with 'name' and 'url' keys
        """
        endpoint_url = f"{self.config['api_base_url']}{self.api_endpoint}?limit={DEFAULT_API_LIMIT}"
        return self.api_client.get(endpoint_url).get("results", [])

    def process(
        self, resource_ref: Dict[str, str]
    ) -> Optional[Union[Dict[str, Any], str]]:
        """
        Processes a single item from its API reference.

        This method fetches the full item data, checks if it exists in the target
        generation, and writes it to a JSON file if applicable.

        Args:
            resource_ref: Dictionary containing 'name' and 'url' for the item

        Returns:
            A summary dict with name, id, and sprite, or None if item doesn't exist
            in the target generation, or an error string if processing fails
        """
        try:
            data = self.api_client.get(resource_ref["url"])
            game_indices = data.get("game_indices", [])

            # Skip items with no game indices
            if not game_indices:
                return None

            # Determine which generations this item appears in
            item_generations = {
                int(game_index["generation"]["url"].split("/")[-2])
                for game_index in game_indices
            }

            # Only process if item exists in the target generation
            if self.target_gen is not None and self.target_gen in item_generations:
                # Extract fling effect name if it exists
                fling_effect_obj = data.get("fling_effect")
                fling_effect_name = (
                    fling_effect_obj.get("name") if fling_effect_obj else None
                )

                cleaned_data = {
                    "id": data["id"],
                    "name": data["name"],
                    "source_url": resource_ref["url"],
                    "cost": data["cost"],
                    "fling_power": data["fling_power"],
                    "fling_effect": fling_effect_name,
                    "attributes": [attr["name"] for attr in data.get("attributes", [])],
                    "category": data.get("category", {}).get("name"),
                    "effect": get_english_entry(
                        data.get("effect_entries", []), "effect"
                    ),
                    "short_effect": get_english_entry(
                        data.get("effect_entries", []), "short_effect"
                    ),
                    "flavor_text": get_all_english_entries_for_gen_by_game(
                        data.get("flavor_text_entries", []),
                        "text",
                        self.generation_version_groups,
                        self.target_gen,
                    ),
                    "sprite": data.get("sprites", {}).get("default"),
                }

                # Write to file
                output_path = self.config[self.output_dir_key]
                write_json_file(output_path, cleaned_data["name"], cleaned_data)

                return {
                    "name": cleaned_data["name"],
                    "id": cleaned_data["id"],
                    "sprite": cleaned_data["sprite"],
                }

            return None

        except (KeyError, ValueError) as e:
            return f"Parsing failed for {resource_ref.get('name', 'unknown')}: {type(e).__name__} - {e}"
        except Exception as e:
            logger.error(
                f"Unexpected error processing {resource_ref.get('name', 'unknown')}: {e}"
            )
            return f"Parsing failed for {resource_ref.get('name', 'unknown')}: {e}"
