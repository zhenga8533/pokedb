"""Backward-compatible imports for the configuration API.

New code should import configuration from :mod:`pokedb.config`.
"""

from ..config import Config, load_config

__all__ = ["Config", "load_config"]
