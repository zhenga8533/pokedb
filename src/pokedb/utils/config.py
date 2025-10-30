"""Configuration management utilities."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .exceptions import ConfigurationError


@dataclass
class Config:
    """
    Validated configuration schema for PokéDB.

    All configuration values are validated upon instantiation to ensure
    required fields exist and have appropriate types.
    """

    api_base_url: str
    timeout: int
    max_retries: int
    max_workers: int
    parser_cache_dir: Optional[str]
    scraper_cache_dir: Optional[str]
    cache_expires: Optional[int]
    output_dir_ability: str
    output_dir_item: str
    output_dir_move: str
    output_dir_pokemon: str
    output_dir_variant: str
    output_dir_transformation: str
    output_dir_cosmetic: str

    def __post_init__(self):
        """Validates configuration values after initialization."""
        if not self.api_base_url:
            raise ConfigurationError("api_base_url cannot be empty")

        if self.timeout <= 0:
            raise ConfigurationError("timeout must be positive")

        if self.max_retries < 0:
            raise ConfigurationError("max_retries cannot be negative")

        if self.max_workers <= 0:
            raise ConfigurationError("max_workers must be positive")

        if self.cache_expires is not None and self.cache_expires < 0:
            raise ConfigurationError("cache_expires cannot be negative")

        # Validate output directories are not empty
        output_dirs = [
            self.output_dir_ability,
            self.output_dir_item,
            self.output_dir_move,
            self.output_dir_pokemon,
            self.output_dir_variant,
            self.output_dir_transformation,
            self.output_dir_cosmetic,
        ]
        for output_dir in output_dirs:
            if not output_dir:
                raise ConfigurationError("output directory paths cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Converts the config back to a dictionary for compatibility."""
        return {
            "api_base_url": self.api_base_url,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "max_workers": self.max_workers,
            "parser_cache_dir": self.parser_cache_dir,
            "scraper_cache_dir": self.scraper_cache_dir,
            "cache_expires": self.cache_expires,
            "output_dir_ability": self.output_dir_ability,
            "output_dir_item": self.output_dir_item,
            "output_dir_move": self.output_dir_move,
            "output_dir_pokemon": self.output_dir_pokemon,
            "output_dir_variant": self.output_dir_variant,
            "output_dir_transformation": self.output_dir_transformation,
            "output_dir_cosmetic": self.output_dir_cosmetic,
        }


def load_config() -> Dict[str, Any]:
    """
    Loads and validates settings from the root config.json file.

    Returns:
        A dictionary containing validated configuration settings

    Raises:
        ConfigurationError: If the config file cannot be found, parsed, or validated
    """
    try:
        # Get the path relative to this file
        config_path = Path(__file__).parent.parent.parent.parent / "config.json"

        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found at {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            raw_config = json.load(f)

        # Validate configuration using the Config dataclass
        try:
            validated_config = Config(**raw_config)
            return validated_config.to_dict()
        except TypeError as e:
            # Missing or extra fields
            raise ConfigurationError(f"Invalid configuration schema: {e}")

    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
    except ConfigurationError:
        # Re-raise ConfigurationError as-is
        raise
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}")
