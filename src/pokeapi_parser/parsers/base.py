from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Union

import requests
from tqdm import tqdm


class BaseParser(ABC):
    """An abstract base class for all parsers."""

    def __init__(
        self,
        config: Dict[str, Any],
        session: requests.Session,
        generation_version_groups: Optional[Dict[int, List[str]]] = None,
        target_gen: Optional[int] = None,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        """
        Initializes the BaseParser.

        Args:
            config (Dict[str, Any]): The application configuration.
            session (requests.Session): The requests Session for making API calls.
            generation_version_groups (Optional[Dict[int, List[str]]]): Map of generations to version groups.
            target_gen (Optional[int]): The target generation number for parsing.
            generation_dex_map (Optional[Dict[int, str]]): Map of generations to Pokédex names.
        """
        self.config = config
        self.session = session
        self.generation_version_groups = generation_version_groups
        self.target_gen = target_gen
        self.generation_dex_map = generation_dex_map
        self.item_name: str = ""  # e.g., "Ability", "Item"
        self.api_endpoint: str = ""  # e.g., "ability", "item"
        self.output_dir_key: str = ""  # e.g., "output_dir_ability"

    @abstractmethod
    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]], str]]:
        """
        Processes a single item reference from the API's master list.
        This method MUST be implemented by a subclass.

        Args:
            item_ref (Dict[str, str]): A dictionary containing the name and URL of the item to process.

        Returns:
            An object for the summary, a list of summary objects, or an error string.
        """
        pass

    def run(self, all_items: List[Dict[str, str]]) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """
        The main execution logic for a parser. Concurrently processes all items.

        Args:
            all_items (List[Dict[str, str]]): A list of all item references to process.

        Returns:
            A list of summary data dictionaries or a dictionary of summary lists (for PokemonParser).
        """
        print(f"--- Running {self.item_name} Parser ---")
        if not all_items:
            print(f"No {self.item_name.lower()}s to process for this generation")
            return []

        print(f"Found {len(all_items)} {self.item_name.lower()}s. Starting concurrent processing...")
        errors: List[str] = []
        summary_data: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_map = {executor.submit(self.process, item): item for item in all_items}
            for future in tqdm(as_completed(future_map), total=len(all_items), desc=f"Processing {self.item_name}s"):
                result = future.result()
                if isinstance(result, dict):
                    summary_data.append(result)
                elif isinstance(result, list):
                    summary_data.extend(result)
                elif result is not None:
                    errors.append(str(result))

        print(f"\n{self.item_name} processing complete")

        if not errors:
            output_path = self.config.get(self.output_dir_key, "")
            print(f"All {self.item_name.lower()}s successfully parsed and saved to '{output_path}'")

        if errors:
            print("\nThe following errors occurred:")
            for error in errors:
                print(f"- {error}")

        # Sort the summary data by ID before returning
        summary_data.sort(key=lambda x: x["id"])
        return summary_data
