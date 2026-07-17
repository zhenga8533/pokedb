"""Generation index creation and transactional output publishing."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .config import Config
from .utils import write_json_atomic

logger = logging.getLogger(__name__)

DATA_SCHEMA_VERSION = 3

PARSER_OUTPUT_KEYS = {
    "ability": ("output_dir_ability",),
    "item": ("output_dir_item",),
    "move": ("output_dir_move",),
    "pokemon": (
        "output_dir_pokemon",
        "output_dir_variant",
        "output_dir_transformation",
        "output_dir_cosmetic",
    ),
}
PARSER_SUMMARY_KEYS = {
    "ability": ("ability",),
    "item": ("item",),
    "move": ("move",),
    "pokemon": ("pokemon", "variant", "transformation", "cosmetic"),
}
RESOURCE_INDEX_KEYS = tuple(
    key for keys in PARSER_SUMMARY_KEYS.values() for key in keys
)


def write_index_file(
    all_summaries: Dict[str, List[Dict[str, Any]]],
    target_gen: int,
    output_dir: Path,
    generation_version_groups: Dict[int, List[str]],
    api_base_url: str,
    is_historical: bool,
    existing_index: Optional[Dict[str, Any]] = None,
    replaced_keys: Optional[Set[str]] = None,
) -> None:
    """Writes an index, preserving unrequested resources during partial runs."""
    resource_index = dict(existing_index or {})
    resource_index.pop("metadata", None)
    for key in replaced_keys or set():
        resource_index.pop(key, None)
    resource_index.update(all_summaries)
    for key in RESOURCE_INDEX_KEYS:
        resource_index.setdefault(key, [])

    metadata = {
        "schema_version": DATA_SCHEMA_VERSION,
        "source": "pokeapi",
        "api_base_url": api_base_url,
        "is_historical": is_historical,
        "generation": target_gen,
        "version_groups": generation_version_groups.get(target_gen, []),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            key: len(value)
            for key, value in resource_index.items()
            if isinstance(value, list)
        },
    }
    write_json_atomic(
        output_dir / "index.json", {"metadata": metadata, **resource_index}
    )
    logger.info("Top-level index.json created at '%s'", output_dir / "index.json")


def build_staging_config(final_config: Config, staging_root: Path) -> Config:
    """Redirects all configured output directories into a staging tree."""
    return final_config.with_generation_root(staging_root)


def publish_staged_output(staging_root: Path, final_root: Path) -> None:
    """Replaces a generation tree while restoring the old tree on failure."""
    backup_root = final_root.with_name(f".{final_root.name}.backup")
    if backup_root.exists():
        if final_root.exists():
            shutil.rmtree(backup_root)
        else:
            backup_root.replace(final_root)

    if final_root.exists():
        final_root.replace(backup_root)

    try:
        staging_root.replace(final_root)
    except Exception:
        if backup_root.exists() and not final_root.exists():
            backup_root.replace(final_root)
        raise
    else:
        if backup_root.exists():
            shutil.rmtree(backup_root)
