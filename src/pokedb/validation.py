"""Runtime validation for generated generation datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .utils.exceptions import DataValidationError

RESOURCE_PATHS = {
    "ability": Path("ability"),
    "item": Path("item"),
    "move": Path("move"),
    "pokemon": Path("pokemon/default"),
    "variant": Path("pokemon/variant"),
    "transformation": Path("pokemon/transformation"),
    "cosmetic": Path("pokemon/cosmetic"),
}
VERSIONED_MOVE_FIELDS = {
    "accuracy",
    "power",
    "pp",
    "effect_chance",
    "type",
    "effect",
    "short_effect",
}
MODERN_STAT_NAMES = {
    "hp",
    "attack",
    "defense",
    "special-attack",
    "special-defense",
    "speed",
}
GENERATION_ONE_STAT_NAMES = {
    "hp",
    "attack",
    "defense",
    "special",
    "speed",
}
STAT_NAMES = MODERN_STAT_NAMES | GENERATION_ONE_STAT_NAMES


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_optional(value: Any, expected_type: type) -> bool:
    return value is None or isinstance(value, expected_type)


def _require_fields(data: dict[str, Any], fields: set[str], path: Path) -> None:
    missing = fields - set(data)
    if missing:
        raise DataValidationError(f"{path}: missing fields {sorted(missing)}")


def _read_object(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as file:
            value = json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        raise DataValidationError(
            f"Cannot read valid JSON from {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DataValidationError(f"Expected a JSON object in {path}")
    return value


def _validate_version_map(
    data: dict[str, Any], field: str, version_groups: set[str], path: Path
) -> None:
    value = data.get(field)
    if not isinstance(value, dict) or set(value) != version_groups:
        raise DataValidationError(
            f"{path}: {field} must contain exactly the generation version groups"
        )


def _validate_common(
    data: dict[str, Any], expected_name: str, path: Path
) -> None:
    if data.get("name") != expected_name:
        raise DataValidationError(
            f"{path}: name must match its filename ({expected_name!r})"
        )
    if not _is_int(data.get("id")) or data["id"] <= 0:
        raise DataValidationError(f"{path}: id must be a positive integer")
    source_url = data.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith(
        ("http://", "https://")
    ):
        raise DataValidationError(f"{path}: source_url must be an HTTP(S) URL")


def _validate_ability(
    data: dict[str, Any], version_groups: set[str], _generation: int, path: Path
) -> None:
    _require_fields(
        data,
        {"is_main_series", "generation", "effect", "short_effect", "flavor_text"},
        path,
    )
    if not isinstance(data["is_main_series"], bool) or not isinstance(
        data["generation"], str
    ):
        raise DataValidationError(f"{path}: invalid ability flags or generation")
    for field in ("effect", "short_effect"):
        _validate_version_map(data, field, version_groups, path)
        if any(
            value is not None and not isinstance(value, str)
            for value in data[field].values()
        ):
            raise DataValidationError(f"{path}: {field} values must be strings or null")
    if not isinstance(data["flavor_text"], dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in data["flavor_text"].items()
    ):
        raise DataValidationError(f"{path}: flavor_text must be an object")


def _validate_move(
    data: dict[str, Any], version_groups: set[str], _generation: int, path: Path
) -> None:
    _require_fields(
        data,
        VERSIONED_MOVE_FIELDS
        | {
            "priority",
            "damage_class",
            "target",
            "generation",
            "flavor_text",
            "stat_changes",
            "machine",
            "metadata",
        },
        path,
    )
    for field in VERSIONED_MOVE_FIELDS:
        _validate_version_map(data, field, version_groups, path)
    for field in ("accuracy", "power", "pp", "effect_chance"):
        if any(
            value is not None and not _is_int(value)
            for value in data[field].values()
        ):
            raise DataValidationError(f"{path}: invalid numeric {field} values")
    for field in ("type", "effect", "short_effect"):
        if any(
            value is not None and not isinstance(value, str)
            for value in data[field].values()
        ):
            raise DataValidationError(f"{path}: invalid textual {field} values")
    if not _is_int(data.get("priority")):
        raise DataValidationError(f"{path}: priority must be an integer")
    if not all(
        _is_optional(data[field], str)
        for field in ("damage_class", "target", "generation", "machine")
    ):
        raise DataValidationError(f"{path}: invalid move identifiers")
    if not isinstance(data["flavor_text"], dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in data["flavor_text"].items()
    ):
        raise DataValidationError(f"{path}: invalid move flavor_text")
    if not isinstance(data.get("metadata"), dict) or not isinstance(
        data.get("stat_changes"), list
    ):
        raise DataValidationError(f"{path}: invalid move metadata or stat_changes")


def _validate_item(
    data: dict[str, Any], _version_groups: set[str], _generation: int, path: Path
) -> None:
    _require_fields(
        data,
        {
            "cost",
            "fling_power",
            "fling_effect",
            "attributes",
            "category",
            "effect",
            "short_effect",
            "flavor_text",
            "sprite",
        },
        path,
    )
    if not _is_int(data.get("cost")) or data["cost"] < 0:
        raise DataValidationError(f"{path}: cost must be a non-negative integer")
    if data["fling_power"] is not None and not _is_int(data["fling_power"]):
        raise DataValidationError(f"{path}: fling_power must be an integer or null")
    if not all(
        _is_optional(data[field], str)
        for field in ("fling_effect", "category", "effect", "short_effect", "sprite")
    ):
        raise DataValidationError(f"{path}: invalid item text or identifier field")
    if not isinstance(data.get("attributes"), list) or not isinstance(
        data.get("flavor_text"), dict
    ):
        raise DataValidationError(f"{path}: invalid item attributes or flavor_text")
    if not all(isinstance(value, str) for value in data["attributes"]):
        raise DataValidationError(f"{path}: item attributes must be strings")


def _validate_pokemon(
    data: dict[str, Any], version_groups: set[str], generation: int, path: Path
) -> None:
    _require_fields(
        data,
        {
            "species",
            "is_default",
            "types",
            "abilities",
            "stats",
            "ev_yield",
            "height",
            "weight",
            "cries",
            "sprites",
            "base_experience",
            "held_items",
            "moves",
        },
        path,
    )
    if not isinstance(data["species"], str) or not isinstance(data["is_default"], bool):
        raise DataValidationError(f"{path}: invalid species or is_default")
    if not all(
        _is_int(data[field]) and data[field] >= 0
        for field in ("height", "weight")
    ):
        raise DataValidationError(
            f"{path}: height and weight must be non-negative integers"
        )
    if data["base_experience"] is not None and not _is_int(data["base_experience"]):
        raise DataValidationError(f"{path}: base_experience must be an integer or null")
    if not isinstance(data["cries"], dict) or not isinstance(data["sprites"], dict):
        raise DataValidationError(f"{path}: cries and sprites must be objects")
    types = data.get("types")
    if not isinstance(types, list) or not 1 <= len(types) <= 2 or not all(
        isinstance(value, str) for value in types
    ):
        raise DataValidationError(f"{path}: types must contain one or two identifiers")
    stats = data.get("stats")
    expected_stats = (
        GENERATION_ONE_STAT_NAMES if generation == 1 else MODERN_STAT_NAMES
    )
    if not isinstance(stats, dict) or set(stats) != expected_stats or not all(
        _is_int(value) and 1 <= value <= 255 for value in stats.values()
    ):
        raise DataValidationError(
            f"{path}: stats must contain the valid generation-specific base stats"
        )
    abilities = data.get("abilities")
    if not isinstance(abilities, list) or not all(
        isinstance(ability, dict)
        and isinstance(ability.get("name"), str)
        and isinstance(ability.get("is_hidden"), bool)
        and _is_int(ability.get("slot"))
        for ability in abilities
    ):
        raise DataValidationError(f"{path}: invalid abilities")
    ev_yield = data.get("ev_yield")
    if not isinstance(ev_yield, list) or not all(
        isinstance(entry, dict)
        and entry.get("stat") in STAT_NAMES
        and _is_int(entry.get("effort"))
        and entry["effort"] > 0
        for entry in ev_yield
    ):
        raise DataValidationError(f"{path}: invalid EV yield")
    moves = data.get("moves")
    held_items = data.get("held_items")
    if not isinstance(moves, dict) or not isinstance(held_items, dict):
        raise DataValidationError(f"{path}: moves and held_items must be objects")
    for entries in moves.values():
        if not isinstance(entries, list):
            raise DataValidationError(f"{path}: each move method must contain a list")
        for entry in entries:
            groups = entry.get("version_groups") if isinstance(entry, dict) else None
            if not isinstance(groups, list) or not set(groups) <= version_groups:
                raise DataValidationError(f"{path}: move has invalid version groups")

    def validate_evolution_node(node: Any) -> None:
        if not isinstance(node, dict) or not isinstance(
            node.get("species_name"), str
        ) or not isinstance(node.get("evolves_to"), list):
            raise DataValidationError(f"{path}: invalid evolution chain node")
        for evolution in node["evolves_to"]:
            details = evolution.get("evolution_details") if isinstance(
                evolution, dict
            ) else None
            if not isinstance(details, list):
                raise DataValidationError(f"{path}: invalid evolution details")
            for detail in details:
                groups = detail.get("version_groups") if isinstance(
                    detail, dict
                ) else None
                if not isinstance(groups, list) or not set(groups) <= version_groups:
                    raise DataValidationError(
                        f"{path}: evolution has invalid version groups"
                    )
                if not _is_optional(
                    detail.get("introduced_in_version_group"), str
                ):
                    raise DataValidationError(
                        f"{path}: invalid evolution introduction version group"
                    )
            validate_evolution_node(evolution)

    evolution_chain = data.get("evolution_chain")
    if evolution_chain is not None:
        validate_evolution_node(evolution_chain)


VALIDATORS: dict[
    str, Callable[[dict[str, Any], set[str], int, Path], None]
] = {
    "ability": _validate_ability,
    "item": _validate_item,
    "move": _validate_move,
    "pokemon": _validate_pokemon,
    "variant": _validate_pokemon,
    "transformation": _validate_pokemon,
    "cosmetic": _validate_pokemon,
}


def validate_generation_output(generation_root: Path) -> None:
    """Validates schemas, index/file agreement, and core domain invariants."""
    index_path = generation_root / "index.json"
    index = _read_object(index_path)
    metadata = index.get("metadata")
    if not isinstance(metadata, dict):
        raise DataValidationError(f"{index_path}: metadata must be an object")
    version_group_list = metadata.get("version_groups")
    generation = metadata.get("generation")
    if not _is_int(generation) or generation < 1:
        raise DataValidationError(f"{index_path}: generation must be a positive integer")
    if not isinstance(version_group_list, list) or not all(
        isinstance(group, str) for group in version_group_list
    ) or len(version_group_list) != len(set(version_group_list)):
        raise DataValidationError(
            f"{index_path}: version_groups must be unique strings"
        )
    version_groups = set(version_group_list)
    counts = metadata.get("counts")
    if not isinstance(counts, dict):
        raise DataValidationError(f"{index_path}: counts must be an object")

    loaded: dict[str, list[dict[str, Any]]] = {}
    for resource, relative_path in RESOURCE_PATHS.items():
        summaries = index.get(resource)
        if summaries is None:
            continue
        if not isinstance(summaries, list) or counts.get(resource) != len(summaries):
            raise DataValidationError(
                f"{index_path}: invalid {resource} summaries or count"
            )
        names = [entry.get("name") for entry in summaries if isinstance(entry, dict)]
        if len(names) != len(summaries) or any(
            not isinstance(name, str) for name in names
        ):
            raise DataValidationError(f"{index_path}: invalid {resource} summary")
        if len(names) != len(set(names)):
            raise DataValidationError(f"{index_path}: duplicate {resource} names")

        directory = generation_root / relative_path
        files = (
            {path.stem: path for path in directory.glob("*.json")}
            if directory.exists()
            else {}
        )
        if set(names) != set(files):
            raise DataValidationError(
                f"{directory}: files must exactly match the {resource} index"
            )
        loaded[resource] = []
        for summary in summaries:
            path = files[summary["name"]]
            data = _read_object(path)
            _validate_common(data, summary["name"], path)
            if summary.get("id") != data["id"]:
                raise DataValidationError(f"{path}: id differs from its index summary")
            VALIDATORS[resource](data, version_groups, generation, path)
            loaded[resource].append(data)

    if "ability" in loaded:
        ability_names = {entry["name"] for entry in loaded["ability"]}
        for resource in ("pokemon", "variant", "transformation", "cosmetic"):
            for pokemon in loaded.get(resource, []):
                missing = {
                    entry["name"] for entry in pokemon["abilities"]
                } - ability_names
                if missing:
                    raise DataValidationError(
                        f"{pokemon['name']}: unknown abilities {sorted(missing)}"
                    )
