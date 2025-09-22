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
    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]], str]]:
        """Processes a single item reference from the API's master list."""
        pass

    def run(
        self, all_items: Optional[List[Dict[str, str]]] = None
    ) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """The main execution logic for a parser."""
        print(f"--- Running {self.item_name} Parser ---")

        if all_items is None:
            endpoint_url = f"{self.config['api_base_url']}{self.api_endpoint}?limit=3000"
            all_items = self.api_client.get(endpoint_url).get("results", [])

        if not all_items:
            print(f"No {self.item_name.lower()}s to process.")
            return []

        print(f"Found {len(all_items)} {self.item_name.lower()}(s). Starting concurrent processing...")
        errors: List[str] = []
        summary_data: List[Dict[str, Any]] = []
        pokemon_summaries: List[Dict[str, Any]] = []
        form_summaries: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_map = {executor.submit(self.process, item): item for item in all_items}
            for future in tqdm(as_completed(future_map), total=len(all_items), desc=f"Processing {self.item_name}"):
                result = future.result()
                if isinstance(result, dict) and ("pokemon" in result or "form" in result):
                    pokemon_summaries.extend(result.get("pokemon", []))
                    form_summaries.extend(result.get("form", []))
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

        if pokemon_summaries or form_summaries:
            pokemon_summaries.sort(key=lambda x: x.get("id", 0))
            form_summaries.sort(key=lambda x: x.get("id", 0))
            return {"pokemon": pokemon_summaries, "form": form_summaries}

        summary_data.sort(key=lambda x: x.get("id", 0))
        return summary_data
