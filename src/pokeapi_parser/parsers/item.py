import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Union

from tqdm import tqdm

from ..api_client import ApiClient
from ..utils import get_all_english_flavor_texts_for_gen, get_english_entry
from .base import BaseParser


class ItemParser(BaseParser):
    """A parser for Pokémon items."""

    def __init__(
        self,
        config: Dict[str, Any],
        api_client: ApiClient,
        generation_version_groups: Dict[int, List[str]],
        target_gen: int,
        generation_dex_map: Optional[Dict[int, str]] = None,
    ):
        super().__init__(config, api_client, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Item"
        self.api_endpoint = "item"
        self.output_dir_key = "output_dir_item"

    def run(self) -> List[Dict[str, Any]]:
        """The main execution logic for the item parser."""
        print(f"--- Running {self.item_name} Parser ---")

        endpoint_url = f"{self.config['api_base_url']}{self.api_endpoint}?limit=3000"
        all_items = self.api_client.get(endpoint_url).get("results", [])

        if not all_items:
            print(f"No {self.item_name.lower()}s to process.")
            return []

        print(f"Found {len(all_items)} {self.item_name.lower()}(s). Starting concurrent processing...")
        errors: List[str] = []
        summary_data: List[Dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_map = {executor.submit(self.process, item): item for item in all_items}
            for future in tqdm(as_completed(future_map), total=len(all_items), desc=f"Processing {self.item_name}"):
                result = future.result()
                if isinstance(result, dict):
                    summary_data.append(result)
                elif result is not None:
                    errors.append(str(result))

        print(f"\n{self.item_name} processing complete")

        if errors:
            print("\nThe following errors occurred:")
            for error in errors:
                print(f"- {error}")

        summary_data.sort(key=lambda x: x.get("id", 0))
        return summary_data

    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, Any], str]]:
        """Processes a single item from its API reference."""
        try:
            data = self.api_client.get(item_ref["url"])
            game_indices = data.get("game_indices", [])
            if not game_indices:
                return None

            introduction_gen = int(min(gi["generation"]["url"].split("/")[-2] for gi in game_indices))

            if self.target_gen is not None and introduction_gen <= self.target_gen:
                fling_effect_obj = data.get("fling_effect")
                fling_effect_name = fling_effect_obj.get("name") if fling_effect_obj else None
                cleaned_data = {
                    "id": data["id"],
                    "name": data["name"],
                    "source_url": item_ref["url"],
                    "cost": data["cost"],
                    "fling_power": data["fling_power"],
                    "fling_effect": fling_effect_name,
                    "attributes": [attr["name"] for attr in data.get("attributes", [])],
                    "category": data.get("category", {}).get("name"),
                    "effect": get_english_entry(data.get("effect_entries", []), "effect"),
                    "short_effect": get_english_entry(data.get("effect_entries", []), "short_effect"),
                    "flavor_text": get_all_english_flavor_texts_for_gen(
                        data.get("flavor_text_entries", []), self.generation_version_groups, self.target_gen
                    ),
                    "sprite": data.get("sprites", {}).get("default"),
                }

                output_path = self.config[self.output_dir_key]
                os.makedirs(output_path, exist_ok=True)
                file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

                return {"name": cleaned_data["name"], "id": cleaned_data["id"], "sprite": cleaned_data["sprite"]}
            return None
        except Exception as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
