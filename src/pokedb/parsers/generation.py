from typing import Dict, List

from .base import BaseParser


class GenerationParser(BaseParser):
    """
    An abstract base class for parsers that fetch their master list
    by iterating through API generation endpoints.
    """

    def _get_all_item_refs(self) -> List[Dict[str, str]]:
        """Gets all item references from the API by iterating through generations."""
        all_items: List[Dict[str, str]] = []
        if self.target_gen:
            print(f"Collecting all {self.item_name.lower()}s up to Generation {self.target_gen}...")
            for gen_num in range(1, self.target_gen + 1):
                try:
                    gen_data = self.api_client.get(f"{self.config['api_base_url']}generation/{gen_num}")
                    items_in_gen = gen_data.get(self.api_endpoint, [])
                    all_items.extend(items_in_gen)
                except Exception as e:
                    print(f"Warning: Could not fetch {self.item_name} data for Generation {gen_num}. Error: {e}")
        return all_items
