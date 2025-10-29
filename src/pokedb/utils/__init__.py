"""
Utility functions and helpers for the PokemonDB parser.

This package contains:
- exceptions: Custom exception classes
- constants: Constants used throughout the application
- file_ops: File and cache operations
- config: Configuration management
- api_helpers: API interaction helpers
- text_utils: Text parsing and transformation utilities
"""

# Exceptions
from .exceptions import (
    ConfigurationError,
    GenerationNotFoundError,
    PokedexMappingError,
    PokemonDBError,
)

# Constants
from .constants import (
    DEFAULT_API_LIMIT,
    MAX_ROMAN_NUMERAL,
    ROMAN_NUMERAL_MAP,
    SERVER_ERROR_CODES,
)

# File operations
from .file_ops import get_cache_path, write_json_file

# Configuration
from .config import load_config

# API helpers
from .api_helpers import get_generation_dex_map, get_latest_generation

# Text utilities
from .text_utils import (
    build_version_group_to_generation_map,
    get_all_english_entries_by_version,
    get_all_english_entries_for_gen_by_game,
    get_english_entry,
    int_to_roman,
    kebab_to_snake,
    parse_gen_range,
    transform_keys_to_snake_case,
)

__all__ = [
    # Exceptions
    "PokemonDBError",
    "GenerationNotFoundError",
    "PokedexMappingError",
    "ConfigurationError",
    # Constants
    "MAX_ROMAN_NUMERAL",
    "DEFAULT_API_LIMIT",
    "SERVER_ERROR_CODES",
    "ROMAN_NUMERAL_MAP",
    # File operations
    "get_cache_path",
    "write_json_file",
    # Configuration
    "load_config",
    # API helpers
    "get_latest_generation",
    "get_generation_dex_map",
    # Text utilities
    "parse_gen_range",
    "int_to_roman",
    "get_all_english_entries_for_gen_by_game",
    "get_all_english_entries_by_version",
    "build_version_group_to_generation_map",
    "get_english_entry",
    "kebab_to_snake",
    "transform_keys_to_snake_case",
]
