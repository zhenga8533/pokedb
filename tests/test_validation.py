import json

import pytest

from pokedb.utils.exceptions import DataValidationError
from pokedb.validation import RESOURCE_PATHS, validate_generation_output


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_ability_dataset(tmp_path, version_group_key):
    resources = {resource: [] for resource in RESOURCE_PATHS}
    resources["ability"] = [{"name": "stench", "id": 1}]
    _write_json(
        tmp_path / "index.json",
        {
            "metadata": {
                "schema_version": 3,
                "source": "pokeapi",
                "api_base_url": "https://example.test/",
                "is_historical": False,
                "generation": 9,
                "version_groups": ["scarlet-violet"],
                "created_at": "2026-01-01T00:00:00+00:00",
                "counts": {
                    resource: (1 if resource == "ability" else 0)
                    for resource in RESOURCE_PATHS
                },
            },
            **resources,
        },
    )
    _write_json(
        tmp_path / "ability" / "stench.json",
        {
            "id": 1,
            "name": "stench",
            "source_url": "https://example.test/ability/1/",
            "is_main_series": True,
            "generation": "generation-iii",
            "effect": {version_group_key: "Current effect"},
            "short_effect": {version_group_key: "Current short effect"},
            "flavor_text": {},
        },
    )


def test_generation_validation_accepts_consistent_ability_data(tmp_path):
    _write_ability_dataset(tmp_path, "scarlet-violet")

    validate_generation_output(tmp_path)


def test_generation_validation_rejects_rewritten_identifiers(tmp_path):
    _write_ability_dataset(tmp_path, "scarlet_violet")

    with pytest.raises(DataValidationError, match="version groups"):
        validate_generation_output(tmp_path)
