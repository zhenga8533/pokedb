"""Typed application configuration loading and validation."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .utils.exceptions import ConfigurationError

OUTPUT_PATHS = {
    "output_dir_ability": Path("ability"),
    "output_dir_item": Path("item"),
    "output_dir_move": Path("move"),
    "output_dir_pokemon": Path("pokemon/default"),
    "output_dir_variant": Path("pokemon/variant"),
    "output_dir_transformation": Path("pokemon/transformation"),
    "output_dir_cosmetic": Path("pokemon/cosmetic"),
}
@dataclass(frozen=True)
class Config:
    """Validated, immutable settings shared by the application."""

    api_base_url: str
    timeout: int
    max_retries: int
    max_workers: int
    parser_cache_dir: Path | None
    scraper_cache_dir: Path | None
    cache_expires: int | None
    output_root: Path
    generation: int | None = field(default=None, repr=False)
    _generation_root_override: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.api_base_url, str) or not self.api_base_url:
            raise ConfigurationError("api_base_url must be a non-empty string")
        parsed_url = urlsplit(self.api_base_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ConfigurationError("api_base_url must be a valid HTTP(S) URL")
        if not self.api_base_url.endswith("/"):
            raise ConfigurationError("api_base_url must end with '/'")

        for name in ("timeout", "max_retries", "max_workers"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise ConfigurationError(f"{name} must be an integer")
        if self.timeout <= 0:
            raise ConfigurationError("timeout must be positive")
        if self.max_retries < 0:
            raise ConfigurationError("max_retries cannot be negative")
        if self.max_workers <= 0:
            raise ConfigurationError("max_workers must be positive")
        if self.cache_expires is not None:
            if not isinstance(self.cache_expires, int) or isinstance(
                self.cache_expires, bool
            ):
                raise ConfigurationError("cache_expires must be an integer or null")
            if self.cache_expires < 0:
                raise ConfigurationError("cache_expires cannot be negative")
        for name in ("parser_cache_dir", "scraper_cache_dir"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Path):
                raise ConfigurationError(f"{name} must be a path or null")
        if not isinstance(self.output_root, Path):
            raise ConfigurationError("output_root must be a path")
        if self._generation_root_override is not None and not isinstance(
            self._generation_root_override, Path
        ):
            raise ConfigurationError("generation output override must be a path")
        if self.generation is not None:
            if not isinstance(self.generation, int) or isinstance(
                self.generation, bool
            ):
                raise ConfigurationError("generation must be an integer")
            if self.generation < 1:
                raise ConfigurationError("generation must be positive")

    @property
    def generation_output_root(self) -> Path:
        """Returns the active generation directory."""
        if self._generation_root_override is not None:
            return self._generation_root_override
        if self.generation is None:
            raise ConfigurationError(
                "generation output requested before generation setup"
            )
        return self.output_root / f"gen{self.generation}"

    def for_generation(self, generation: int) -> Config:
        """Returns settings scoped to one generation's output tree."""
        return replace(self, generation=generation, _generation_root_override=None)

    def with_generation_root(self, generation_root: Path) -> Config:
        """Returns generation settings redirected to another output tree."""
        if self.generation is None:
            raise ConfigurationError("cannot redirect output before generation setup")
        return replace(self, _generation_root_override=generation_root)

    def without_cache(self) -> Config:
        """Returns settings with all persistent caches disabled."""
        return replace(
            self,
            parser_cache_dir=None,
            scraper_cache_dir=None,
            cache_expires=None,
        )

    def output_path(self, key: str) -> Path:
        """Returns a configured parser output directory by its internal key."""
        try:
            relative_path = OUTPUT_PATHS[key]
        except KeyError as error:
            raise KeyError(f"Unknown output directory key: {key}") from error
        return self.generation_output_root / relative_path

    def to_dict(self) -> dict[str, Any]:
        """Returns the user-configurable values in JSON-compatible form."""
        values = asdict(self)
        values.pop("generation")
        values.pop("_generation_root_override")
        for key in ("parser_cache_dir", "scraper_cache_dir", "output_root"):
            if values[key] is not None:
                values[key] = str(values[key])
        return values

def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as config_file:
            value = json.load(config_file)
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file not found at {path}") from error
    except json.JSONDecodeError as error:
        raise ConfigurationError(
            f"Invalid JSON in configuration file: {error}"
        ) from error
    except OSError as error:
        raise ConfigurationError(
            f"Could not read configuration file {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise ConfigurationError("Configuration must be a JSON object")
    return value


def _normalize_legacy_output_paths(overrides: dict[str, Any]) -> dict[str, Any]:
    """Converts the previous full output-path schema to ``output_root``."""
    legacy_keys = set(OUTPUT_PATHS).intersection(overrides)
    if not legacy_keys:
        return overrides
    if legacy_keys != set(OUTPUT_PATHS):
        raise ConfigurationError(
            "Legacy output configuration must include every output_dir_* setting; "
            "prefer the new output_root setting"
        )
    if "output_root" in overrides:
        raise ConfigurationError(
            "Use output_root or legacy output_dir_* settings, not both"
        )

    legacy_paths = {key: Path(str(overrides[key])) for key in OUTPUT_PATHS}
    generation_dir = legacy_paths["output_dir_ability"].parent
    if generation_dir.name != "gen{gen_num}":
        raise ConfigurationError(
            "Legacy output paths must use the gen{gen_num} directory convention"
        )
    output_root = generation_dir.parent
    for key, relative_path in OUTPUT_PATHS.items():
        expected = output_root / "gen{gen_num}" / relative_path
        if legacy_paths[key] != expected:
            raise ConfigurationError(
                "Legacy output directories must share one generation output root"
            )

    normalized = {
        key: value for key, value in overrides.items() if key not in OUTPUT_PATHS
    }
    normalized["output_root"] = str(output_root)
    return normalized


def _resolve_path(value: Any, name: str, base_dir: Path, nullable: bool) -> Path | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        suffix = " or null" if nullable else ""
        raise ConfigurationError(f"{name} must be a non-empty path string{suffix}")
    path = Path(value).expanduser()
    return path if path.is_absolute() else (base_dir / path).resolve()


def load_config(config_path: str | Path | None = None) -> Config:
    """Loads defaults plus optional CLI/environment overrides and validates them."""
    default_resource = files("pokedb").joinpath("default_config.json")
    try:
        with default_resource.open("r", encoding="utf-8") as config_file:
            defaults = json.load(config_file)
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigurationError(
            f"Could not load packaged defaults: {error}"
        ) from error
    if not isinstance(defaults, dict):
        raise ConfigurationError("Packaged defaults must be a JSON object")

    configured_path = config_path or os.environ.get("POKEDB_CONFIG")
    if configured_path is None:
        raw_config = defaults
        base_dir = Path.cwd()
    else:
        resolved_path = Path(configured_path).expanduser().resolve()
        overrides = _normalize_legacy_output_paths(_read_json(resolved_path))
        raw_config = defaults | overrides
        base_dir = resolved_path.parent

    raw_config = dict(raw_config)
    raw_config["parser_cache_dir"] = _resolve_path(
        raw_config.get("parser_cache_dir"), "parser_cache_dir", base_dir, True
    )
    raw_config["scraper_cache_dir"] = _resolve_path(
        raw_config.get("scraper_cache_dir"), "scraper_cache_dir", base_dir, True
    )
    raw_config["output_root"] = _resolve_path(
        raw_config.get("output_root"), "output_root", base_dir, False
    )
    try:
        return Config(**raw_config)
    except TypeError as error:
        raise ConfigurationError(f"Invalid configuration schema: {error}") from error
