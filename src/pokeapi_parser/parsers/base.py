import os
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm


class BaseParser(ABC):
    """An abstract base class for all parsers."""

    def __init__(self, config, session, generation_version_groups, target_gen: int):
        self.config = config
        self.session = session
        self.generation_version_groups = generation_version_groups
        self.target_gen = target_gen
        self.item_name = ""  # e.g., "Ability", "Item"
        self.api_endpoint = ""  # e.g., "ability", "item"
        self.output_dir_key = ""  # e.g., "output_dir_ability"

    @abstractmethod
    def process(self, item_ref):
        """
        Processes a single item reference from the API's master list.
        This method MUST be implemented by a subclass.
        It should return a dictionary for the summary or an error string.
        """
        pass

    def run(self, all_items):
        """The main execution logic for a parser, returns rich summary data."""
        print(f"--- Running {self.item_name} Parser ---")
        if not all_items:
            print(f"No {self.item_name.lower()}s to process for this generation")
            return []

        print(f"Found {len(all_items)} {self.item_name.lower()}s. Starting concurrent processing...")
        errors = []
        summary_data = []

        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_map = {executor.submit(self.process, item): item for item in all_items}
            for future in tqdm(as_completed(future_map), total=len(all_items), desc=f"Processing {self.item_name}s"):
                result = future.result()
                if isinstance(result, dict):
                    summary_data.append(result)
                elif result is not None:
                    errors.append(result)

        print(f"\n{self.item_name} processing complete")

        if not errors:
            output_path = self.config[self.output_dir_key]
            print(f"All {self.item_name.lower()}s successfully parsed and saved to '{os.path.abspath(output_path)}'")

        if errors:
            print("\nThe following errors occurred:")
            for error in errors:
                print(f"- {error}")

        # Sort the summary data by ID before returning
        summary_data.sort(key=lambda x: x["id"])
        return summary_data
