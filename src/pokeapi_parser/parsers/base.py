from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

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

    @abstractmethod
    def run(self) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """The main execution logic for a parser."""
        pass
