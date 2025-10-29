from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from logging import getLogger
from typing import Any, Dict, List, Optional, Union

from tqdm import tqdm

from ..api_client import ApiClient

logger = getLogger(__name__)


class PokemonCategory(str, Enum):
    """Categories for different types of Pokémon entries."""

    POKEMON = "pokemon"
    VARIANT = "variant"
    TRANSFORMATION = "transformation"
    COSMETIC = "cosmetic"


class BaseParser(ABC):
    """
    An abstract base class for all API resource parsers.

    This class provides the common infrastructure for parsing different types of
    resources from the PokéAPI (abilities, moves, items, Pokémon, etc.).

    Features:
    - Concurrent processing using ThreadPoolExecutor
    - Progress tracking with tqdm
    - Error handling and reporting
    - Consistent return format
    """

    def __init__(
        self,
        config: Dict[str, Any],
        api_client: ApiClient,
        generation_version_groups: Optional[Dict[int, List[str]]] = None,
        target_gen: Optional[int] = None,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        """
        Initializes the BaseParser with configuration and dependencies.

        Args:
            config: Configuration dictionary with parser settings
            api_client: The API client instance for making requests
            generation_version_groups: Optional mapping of generation numbers to version groups
            target_gen: Optional target generation number to filter data
            generation_dex_map: Optional mapping of generation to regional Pokédex name
        """
        self.config = config
        self.api_client = api_client
        self.generation_version_groups = generation_version_groups
        self.target_gen = target_gen
        self.generation_dex_map = generation_dex_map

        # These must be set by subclasses
        self.entity_type: str = ""  # Human-readable type name (e.g., "Ability", "Move")
        self.api_endpoint: str = ""  # API endpoint name (e.g., "ability", "move")
        self.output_dir_key: str = ""  # Config key for output directory

    @abstractmethod
    def _get_all_item_refs(self) -> List[Dict[str, str]]:
        """
        Retrieves all resource references from the API for this parser.

        Returns:
            A list of dictionaries containing 'name' and 'url' keys for each resource
        """
        pass

    @abstractmethod
    def process(
        self, resource_ref: Dict[str, str]
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]], str]]:
        """
        Processes a single resource reference from the API.

        This method is called concurrently for each resource reference retrieved
        by _get_all_item_refs(). It should fetch the full data, transform it,
        write it to a file, and return summary data.

        Args:
            resource_ref: A dictionary with 'name' and 'url' keys

        Returns:
            - For most parsers: A dict with summary info (name, id, etc.)
            - For Pokemon parser: A dict with category keys mapping to lists
            - On error: A string describing the error
            - None to skip this resource
        """
        pass

    def run(self) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """
        The main execution logic that orchestrates the parsing process.

        This method:
        1. Fetches all resource references
        2. Processes them concurrently using ThreadPoolExecutor
        3. Collects summary data and errors
        4. Returns formatted results

        Returns:
            For most parsers: A sorted list of summary dicts
            For Pokemon parser: A dict with category keys mapping to sorted lists
        """
        logger.info(f"--- Running {self.entity_type} Parser ---")

        all_references = self._get_all_item_refs()

        if not all_references:
            logger.warning(f"No {self.entity_type.lower()}s to process.")
            return [] if "pokemon" not in self.api_endpoint else {}

        logger.info(
            f"Found {len(all_references)} {self.entity_type.lower()}(s). Starting concurrent processing..."
        )
        errors: List[str] = []
        summary_data: List[Dict[str, Any]] = []

        # Initialize Pokemon-specific summaries using the enum
        pokemon_summaries: Dict[str, List[Dict[str, Any]]] = {
            category.value: [] for category in PokemonCategory
        }

        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            # Submit all processing tasks
            future_map = {
                executor.submit(self.process, ref): ref for ref in all_references
            }

            # Collect results as they complete
            for future in tqdm(
                as_completed(future_map),
                total=len(all_references),
                desc=f"Processing {self.entity_type}",
            ):
                result = future.result()

                # Handle Pokemon-specific results (dict with category keys)
                if isinstance(result, dict) and any(
                    key in result for key in pokemon_summaries
                ):
                    for category_key in pokemon_summaries:
                        pokemon_summaries[category_key].extend(
                            result.get(category_key, [])
                        )
                # Handle regular summary result
                elif isinstance(result, dict):
                    summary_data.append(result)
                # Handle list results
                elif isinstance(result, list):
                    summary_data.extend(result)
                # Handle error strings
                elif result is not None:
                    errors.append(str(result))

        logger.info(f"{self.entity_type} processing complete")

        # Report any errors that occurred
        if errors:
            logger.warning(f"\n{len(errors)} error(s) occurred during processing:")
            for error in errors:
                logger.error(f"  - {error}")

        # Return Pokemon-specific results if any were found
        if any(pokemon_summaries.values()):
            # Sort each category by ID
            for category_key in pokemon_summaries:
                pokemon_summaries[category_key].sort(key=lambda x: x.get("id", 0))
            # Return only non-empty categories
            return {key: value for key, value in pokemon_summaries.items() if value}

        # Return regular summary results
        summary_data.sort(key=lambda x: x.get("id", 0))
        return summary_data
