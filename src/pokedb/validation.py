"""Runtime validation for generated generation datasets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .output import DATA_SCHEMA_VERSION, RESOURCE_INDEX_KEYS
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
    data: dict[str, Any], expected_name: str, api_base_url: str, path: Path
) -> None:
    if data.get("name") != expected_name:
        raise DataValidationError(
            f"{path}: name must match its filename ({expected_name!r})"
        )
    if not _is_int(data.get("id")) or data["id"] <= 0:
        raise DataValidationError(f"{path}: id must be a positive integer")
    source_url = data.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith(api_base_url):
        raise DataValidationError(
            f"{path}: source_url must use the configured PokéAPI base URL"
        )


def _validate_ability(
    data: dict[str, Any],
    version_groups: set[str],
    _generation: int,
    _is_historical: bool,
    path: Path,
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
    data: dict[str, Any],
    version_groups: set[str],
    generation: int,
    is_historical: bool,
    path: Path,
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
    if is_historical:
        if data.get("priority") is not None:
            raise DataValidationError(f"{path}: historical priority must be null")
        if any(
            data.get(field) is not None
            for field in ("target", "metadata", "stat_changes")
        ):
            raise DataValidationError(
                f"{path}: unversioned historical move fields must be null"
            )
        damage_class = data.get("damage_class")
        if generation < 4:
            if damage_class not in {None, "physical", "special", "status"}:
                raise DataValidationError(f"{path}: invalid derived damage class")
        elif damage_class is not None:
            raise DataValidationError(f"{path}: historical damage_class must be null")
    elif not _is_int(data.get("priority")):
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
    if not is_historical and (
        not isinstance(data.get("metadata"), dict)
        or not isinstance(data.get("stat_changes"), list)
    ):
        raise DataValidationError(f"{path}: invalid move metadata or stat_changes")


def _validate_item(
    data: dict[str, Any],
    _version_groups: set[str],
    _generation: int,
    is_historical: bool,
    path: Path,
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
    if is_historical:
        current_only_fields = {
            "cost",
            "fling_power",
            "fling_effect",
            "attributes",
            "category",
            "effect",
            "short_effect",
            "sprite",
        }
        if any(data.get(field) is not None for field in current_only_fields):
            raise DataValidationError(
                f"{path}: current-only historical item fields must be null"
            )
        if not isinstance(data.get("flavor_text"), dict):
            raise DataValidationError(f"{path}: invalid item flavor_text")
        return
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
    data: dict[str, Any],
    version_groups: set[str],
    generation: int,
    is_historical: bool,
    path: Path,
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
    if (is_historical and data["cries"] is not None) or (
        not is_historical and not isinstance(data["cries"], dict)
    ) or not isinstance(data["sprites"], dict):
        raise DataValidationError(f"{path}: invalid generation-specific media")
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
    if generation < 3 and abilities:
        raise DataValidationError(
            f"{path}: abilities must be empty before Generation 3"
        )
    ev_yield = data.get("ev_yield")
    if generation < 3:
        if ev_yield is not None:
            raise DataValidationError(
                f"{path}: EV yield must be null before Generation 3"
            )
    elif not isinstance(ev_yield, list) or not all(
        isinstance(entry, dict)
        and entry.get("stat") in STAT_NAMES
        and _is_int(entry.get("effort"))
        and entry["effort"] > 0
        for entry in ev_yield
    ):
        raise DataValidationError(f"{path}: invalid EV yield")
    if is_historical:
        for field in (
            "base_experience",
            "base_happiness",
            "capture_rate",
            "hatch_counter",
            "gender_rate",
            "egg_groups",
            "growth_rate",
            "forms_switchable",
        ):
            if field in data and data[field] is not None:
                raise DataValidationError(
                    f"{path}: current-only historical field {field} must be null"
                )
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
            availability = evolution.get("availability") if isinstance(
                evolution, dict
            ) else None
            if availability not in {"available", "unavailable"}:
                raise DataValidationError(f"{path}: invalid evolution availability")
            details = evolution.get("evolution_details") if isinstance(
                evolution, dict
            ) else None
            if not isinstance(details, list):
                raise DataValidationError(f"{path}: invalid evolution details")
            if (availability == "available") != bool(details):
                raise DataValidationError(
                    f"{path}: evolution availability disagrees with its details"
                )
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
                if detail.get("time_of_day") == "":
                    raise DataValidationError(
                        f"{path}: empty evolution time_of_day must be null"
                    )
            validate_evolution_node(evolution)

    evolution_chain = data.get("evolution_chain")
    if evolution_chain is not None:
        validate_evolution_node(evolution_chain)


VALIDATORS: dict[
    str, Callable[[dict[str, Any], set[str], int, bool, Path], None]
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
    schema_version = metadata.get("schema_version")
    source = metadata.get("source")
    api_base_url = metadata.get("api_base_url")
    is_historical = metadata.get("is_historical")
    if schema_version != DATA_SCHEMA_VERSION:
        raise DataValidationError(
            f"{index_path}: schema_version must be {DATA_SCHEMA_VERSION}"
        )
    if source != "pokeapi":
        raise DataValidationError(f"{index_path}: source must be pokeapi")
    if not isinstance(api_base_url, str) or not api_base_url.endswith("/"):
        raise DataValidationError(f"{index_path}: invalid api_base_url")
    if not isinstance(is_historical, bool):
        raise DataValidationError(f"{index_path}: is_historical must be boolean")
    if not _is_int(generation) or generation < 1:
        raise DataValidationError(f"{index_path}: generation must be a positive integer")
    if (
        not isinstance(version_group_list, list)
        or not all(isinstance(group, str) for group in version_group_list)
        or len(version_group_list) != len(set(version_group_list))
    ):
        raise DataValidationError(
            f"{index_path}: version_groups must be unique strings"
        )
    version_groups = set(version_group_list)
    counts = metadata.get("counts")
    if not isinstance(metadata.get("created_at"), str):
        raise DataValidationError(f"{index_path}: created_at must be a string")
    if not isinstance(counts, dict) or set(counts) != set(RESOURCE_INDEX_KEYS):
        raise DataValidationError(f"{index_path}: counts must be an object")
    if set(index) != {"metadata", *RESOURCE_INDEX_KEYS}:
        raise DataValidationError(
            f"{index_path}: resource keys must use the complete stable schema"
        )

    loaded: dict[str, list[dict[str, Any]]] = {}
    for resource, relative_path in RESOURCE_PATHS.items():
        summaries = index.get(resource)
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
            _validate_common(data, summary["name"], api_base_url, path)
            if summary.get("id") != data["id"]:
                raise DataValidationError(f"{path}: id differs from its index summary")
            VALIDATORS[resource](
                data, version_groups, generation, is_historical, path
            )
            loaded[resource].append(data)

    if loaded.get("ability"):
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

    move_names = {entry["name"] for entry in loaded.get("move", [])}
    item_names = {entry["name"] for entry in loaded.get("item", [])}
    species_names = {entry["species"] for entry in loaded.get("pokemon", [])}

    def validate_evolution_references(node: Any, owner: str) -> None:
        if not isinstance(node, dict):
            return
        species_name = node.get("species_name")
        if species_names and species_name not in species_names:
            raise DataValidationError(
                f"{owner}: evolution chain references unknown species {species_name!r}"
            )
        for evolution in node.get("evolves_to", []):
            for detail in evolution.get("evolution_details", []):
                for field in ("item", "held_item"):
                    reference = detail.get(field)
                    if (
                        item_names
                        and reference is not None
                        and reference not in item_names
                    ):
                        raise DataValidationError(
                            f"{owner}: evolution references unknown item {reference!r}"
                        )
                known_move = detail.get("known_move")
                if (
                    move_names
                    and known_move is not None
                    and known_move not in move_names
                ):
                    raise DataValidationError(
                        f"{owner}: evolution references unknown move {known_move!r}"
                    )
            validate_evolution_references(evolution, owner)

    for resource in ("pokemon", "variant", "transformation", "cosmetic"):
        for pokemon in loaded.get(resource, []):
            if move_names:
                referenced_moves = {
                    move["name"]
                    for method in pokemon["moves"].values()
                    for move in method
                }
                missing_moves = referenced_moves - move_names
                if missing_moves:
                    raise DataValidationError(
                        f"{pokemon['name']}: unknown moves {sorted(missing_moves)}"
                    )
            if item_names:
                missing_items = set(pokemon["held_items"]) - item_names
                if missing_items:
                    raise DataValidationError(
                        f"{pokemon['name']}: unknown held items {sorted(missing_items)}"
                    )
            validate_evolution_references(
                pokemon.get("evolution_chain"), pokemon["name"]
            )

    if item_names:
        for move in loaded.get("move", []):
            machine = move.get("machine")
            if machine is not None and machine not in item_names:
                raise DataValidationError(
                    f"{move['name']}: unknown machine item {machine!r}"
                )
