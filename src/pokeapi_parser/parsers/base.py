import json
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
        """The main execution logic for a parser."""
        print(f"Starting the {self.item_name} Parser...")
        master_list_url = f"{self.config['api_base_url']}{self.api_endpoint}?limit=3000"

        print(f"Fetching master list of {self.item_name.lower()}s...")
        try:
            response = self.session.get(master_list_url, timeout=self.config["timeout"])
            response.raise_for_status()
            all_items = response.json()["results"]
        except Exception as e:
            print(f"Fatal: Could not fetch {self.item_name.lower()} list. {e}")
            return

        print(f"Found {len(all_items)} {self.item_name.lower()}s. Starting concurrent processing...")
        errors = []
        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_map = {executor.submit(self.process, item): item for item in all_items}
            for future in tqdm(as_completed(future_map), total=len(all_items), desc=f"Processing {self.item_name}s"):
                result = future.result()
                if result:
                    errors.append(result)

        print(f"\n{self.item_name} processing complete.")

        if not errors:
            self._create_summary_file(all_items)

        if errors:
            print("\nThe following errors occurred:")
            for error in errors:
                print(f"- {error}")
        else:
            output_path = self.config[self.output_dir_key]
            print(f"All {self.item_name.lower()}s successfully parsed and saved to '{os.path.abspath(output_path)}'.")

    def _create_summary_file(self, all_items):
        """Creates the summary.json file for the category."""
        print(f"Creating summary file for {self.item_name.lower()}s...")
        summary_data = [{"name": item["name"], "id": int(item["url"].split("/")[-2])} for item in all_items]
        output_path = self.config[self.output_dir_key]
        summary_file_path = os.path.join(output_path, "summary.json")

        with open(summary_file_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=4, ensure_ascii=False)
        print("Summary file created successfully.")
