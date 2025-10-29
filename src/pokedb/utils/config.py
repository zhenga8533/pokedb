"""Configuration management utilities."""

import json
from pathlib import Path
from typing import Any, Dict

from .exceptions import ConfigurationError


def load_config() -> Dict[str, Any]:
    """
    Loads settings from the root config.json file.

    Returns:
        A dictionary containing configuration settings

    Raises:
        ConfigurationError: If the config file cannot be found or parsed
    """
    try:
        # Get the path relative to this file
        config_path = Path(__file__).parent.parent.parent.parent / "config.json"

        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found at {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}")
