import json
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from pokedb.config import load_config
from pokedb.utils.exceptions import ConfigurationError


def write_config(path: Path, values: dict) -> Path:
    path.write_text(json.dumps(values), encoding="utf-8")
    return path


def test_load_config_uses_packaged_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.api_base_url == "https://pokeapi.co/api/v2/"
    assert config.max_workers > 0
    assert config.output_root == tmp_path / ".output"
    assert config.parser_cache_dir == tmp_path / ".cache/parser"


def test_custom_config_is_a_partial_override_relative_to_its_directory(tmp_path):
    config_path = write_config(
        tmp_path / "config.json",
        {"max_workers": 2, "output_root": "generated"},
    )

    config = load_config(config_path)

    assert config.max_workers == 2
    assert config.timeout == 15
    assert config.output_root == tmp_path / "generated"
    assert config.parser_cache_dir == tmp_path / ".cache/parser"


def test_explicit_path_takes_precedence_over_environment(monkeypatch, tmp_path):
    environment_path = write_config(tmp_path / "environment.json", {"max_workers": 2})
    explicit_path = write_config(tmp_path / "explicit.json", {"max_workers": 4})
    monkeypatch.setenv("POKEDB_CONFIG", str(environment_path))

    assert load_config(explicit_path).max_workers == 4


def test_environment_path_is_used_without_explicit_path(monkeypatch, tmp_path):
    config_path = write_config(tmp_path / "environment.json", {"max_workers": 3})
    monkeypatch.setenv("POKEDB_CONFIG", str(config_path))

    assert load_config().max_workers == 3


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"timeout": 0}, "timeout must be positive"),
        ({"max_retries": -1}, "max_retries cannot be negative"),
        ({"max_workers": True}, "max_workers must be an integer"),
        ({"cache_expires": -1}, "cache_expires cannot be negative"),
        ({"api_base_url": "not-a-url/"}, "valid HTTP(S) URL"),
        ({"unknown": 1}, "Invalid configuration schema"),
    ],
)
def test_invalid_overrides_are_rejected(tmp_path, override, message):
    config_path = write_config(tmp_path / "config.json", override)

    with pytest.raises(ConfigurationError, match=re.escape(message)):
        load_config(config_path)


def test_malformed_json_is_rejected(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("not json", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Invalid JSON"):
        load_config(config_path)


def test_nullable_cache_paths_disable_caching(tmp_path):
    config_path = write_config(
        tmp_path / "config.json",
        {"parser_cache_dir": None},
    )

    config = load_config(config_path)

    assert config.parser_cache_dir is None


def test_config_is_immutable():
    config = load_config()

    with pytest.raises(FrozenInstanceError):
        config.max_workers = 1


def test_generation_output_paths_are_derived_from_output_root(tmp_path):
    config_path = write_config(tmp_path / "config.json", {"output_root": "generated"})

    config = load_config(config_path).for_generation(3)

    assert config.generation_output_root == tmp_path / "generated/gen3"
    assert config.output_path("output_dir_ability") == (
        tmp_path / "generated/gen3/ability"
    )
    assert config.output_path("output_dir_variant") == (
        tmp_path / "generated/gen3/pokemon/variant"
    )


def test_no_cache_returns_a_new_config():
    config = load_config()

    uncached = config.without_cache()

    assert uncached is not config
    assert uncached.parser_cache_dir is None
    assert uncached.cache_expires is None


def test_removed_scraper_config_is_rejected(tmp_path):
    config_path = write_config(
        tmp_path / "config.json", {"scraper_cache_dir": ".cache/scraper"}
    )

    with pytest.raises(ConfigurationError, match="Invalid configuration schema"):
        load_config(config_path)
