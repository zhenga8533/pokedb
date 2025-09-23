from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Union

from tqdm import tqdm

from .base import BaseParser


class GenerationParser(BaseParser):
    """
    An abstract base class for parsers that fetch their master list
    by iterating through API generation endpoints.
    """

    def run(self) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """The main execution logic for a generation-fetching parser."""
        print(f"--- Running {self.item_name} Parser ---")

        all_items: List[Dict[str, str]] = []
        if self.target_gen:
            print(f"Collecting all {self.item_name.lower()}s up to Generation {self.target_gen}...")
            for gen_num in range(1, self.target_gen + 1):
                try:
                    gen_data = self.api_client.get(f"{self.config['api_base_url']}generation/{gen_num}")
                    endpoint_key = (
                        self.api_endpoint.replace("-", "_") if "species" in self.api_endpoint else self.api_endpoint
                    )
                    items_in_gen = gen_data.get(endpoint_key, [])
                    all_items.extend(items_in_gen)
                except Exception as e:
                    print(f"Warning: Could not fetch {self.item_name} data for Generation {gen_num}. Error: {e}")

        if not all_items:
            print(f"No {self.item_name.lower()}s to process.")
            return [] if "pokemon" not in self.api_endpoint else {}

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
