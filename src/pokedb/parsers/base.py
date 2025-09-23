from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Union

from tqdm import tqdm

from ..api_client import ApiClient


class BaseParser(ABC):
    """An abstract base class for all parsers."""

    def __init__(
        self,
        config: Dict[str, Any],
        api_client: ApiClient,
        generation_version_groups: Optional[Dict[int, List[str]]] = None,
        target_gen: Optional[int] = None,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        """Initializes the BaseParser."""
        self.config = config
        self.api_client = api_client
        self.generation_version_groups = generation_version_groups
        self.target_gen = target_gen
        self.generation_dex_map = generation_dex_map
        self.item_name: str = ""
        self.api_endpoint: str = ""
        self.output_dir_key: str = ""

    @abstractmethod
    def _get_all_item_refs(self) -> List[Dict[str, str]]:
        """Gets all item references from the API."""
        pass

    @abstractmethod
    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]], str]]:
        """Processes a single item reference from the API's master list."""
        pass

    def run(self) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """The main execution logic for a parser."""
        print(f"--- Running {self.item_name} Parser ---")

        all_items = self._get_all_item_refs()

        if not all_items:
            print(f"No {self.item_name.lower()}s to process.")
            return [] if "pokemon" not in self.api_endpoint else {}

        print(f"Found {len(all_items)} {self.item_name.lower()}(s). Starting concurrent processing...")
        errors: List[str] = []
        summary_data: List[Dict[str, Any]] = []
        pokemon_summaries: Dict[str, List[Dict[str, Any]]] = {
            "pokemon": [],
            "variant": [],
            "transformation": [],
            "cosmetic": [],
        }

        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_map = {executor.submit(self.process, item): item for item in all_items}
            for future in tqdm(as_completed(future_map), total=len(all_items), desc=f"Processing {self.item_name}"):
                result = future.result()
                if isinstance(result, dict) and any(key in result for key in pokemon_summaries):
                    for key in pokemon_summaries:
                        pokemon_summaries[key].extend(result.get(key, []))
                elif isinstance(result, dict):
                    summary_data.append(result)
                elif isinstance(result, list):
                    summary_data.extend(result)
                elif result is not None:
                    errors.append(str(result))

        print(f"\n{self.item_name} processing complete")

        if errors:
            print("\nThe following errors occurred:")
            for error in errors:
                print(f"- {error}")

        if any(pokemon_summaries.values()):
            for key in pokemon_summaries:
                pokemon_summaries[key].sort(key=lambda x: x.get("id", 0))
            return {key: value for key, value in pokemon_summaries.items() if value}

        summary_data.sort(key=lambda x: x.get("id", 0))
        return summary_data
