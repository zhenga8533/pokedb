import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm


class BaseParser(ABC):
    """An abstract base class for all parsers."""

    def __init__(self, config, session):
        self.config = config
        self.session = session
        self.item_name = ""  # e.g., "Ability", "Item"
        self.api_endpoint = ""  # e.g., "ability", "item"
        self.output_dir_key = ""  # e.g., "output_dir_ability"

    @abstractmethod
    def process(self, item_ref):
        """
        Processes a single item reference from the API's master list.
        This method MUST be implemented by a subclass.
        """
        pass

    def run(self):
        """The main execution logic for a parser, returns summary data."""
        print(f"Starting the {self.item_name} Parser...")
        master_list_url = f"{self.config['api_base_url']}{self.api_endpoint}?limit=3000"

        print(f"Fetching master list of {self.item_name.lower()}s...")
        try:
            response = self.session.get(master_list_url, timeout=self.config["timeout"])
            response.raise_for_status()
            all_items = response.json()["results"]
        except Exception as e:
            print(f"Fatal: Could not fetch {self.item_name.lower()} list. {e}")
            return None

        print(f"Found {len(all_items)} {self.item_name.lower()}s. Starting concurrent processing...")
        errors = []
        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_map = {executor.submit(self.process, item): item for item in all_items}
            for future in tqdm(as_completed(future_map), total=len(all_items), desc=f"Processing {self.item_name}s"):
                result = future.result()
                if result:
                    errors.append(result)

        print(f"\n{self.item_name} processing complete.")

        summary_data = None
        if not errors:
            summary_data = [{"name": item["name"], "id": int(item["url"].split("/")[-2])} for item in all_items]
            output_path = self.config[self.output_dir_key]
            print(f"All {self.item_name.lower()}s successfully parsed and saved to '{os.path.abspath(output_path)}'.")

        if errors:
            print("\nThe following errors occurred:")
            for error in errors:
                print(f"- {error}")

        return summary_data
