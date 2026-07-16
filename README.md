# PokéDB - Pokémon Data Collector

[![Update Pokémon Data](https://github.com/zhenga8533/pokedb/actions/workflows/update-data.yaml/badge.svg)](https://github.com/zhenga8533/pokedb/actions/workflows/update-data.yaml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python tool for creating a comprehensive, generation-accurate Pokémon database. It combines data from [PokéAPI](https://pokeapi.co/) with historical changes from [Pokémon DB](https://pokemondb.net/).

Parsed generation data is automatically saved to the `data` branch weekly.

## Architecture

```text
pokedb/
|-- src/
|   `-- pokedb/
|       |-- __main__.py          # CLI and generation workflow
|       |-- api_client.py        # API client and caching
|       |-- config.py            # Typed configuration and validation
|       |-- default_config.json  # Packaged default values
|       |-- output.py            # Transactional output publishing
|       |-- runner.py            # Parser orchestration and metadata
|       |-- scraper.py           # Historical data scraper
|       |-- validation.py        # Runtime output schema and integrity checks
|       |-- parsers/             # Ability, item, move, and Pokémon parsers
|       `-- utils/               # Focused shared helpers
|-- tests/
`-- pyproject.toml               # Package metadata and dependencies
```

## Core Features

- Combines structured PokéAPI data with historical Pokémon DB data.
- Reconstructs generation-specific types, abilities, stats, EV yields, and more.
- Processes resources concurrently.
- Builds output in staging and publishes only complete successful runs.
- Generates data for the latest, a specific, or every generation.
- Writes structured JSON with a generation-level index.

## Quick Start

```bash
git clone https://github.com/zhenga8533/pokedb.git
cd pokedb
pip install -e .

# Parse every resource for the latest generation
python -m pokedb --all

# Parse selected resources
python -m pokedb ability move item pokemon

# Parse a historical generation
python -m pokedb --all --gen 3

# Parse without persistent caches
python -m pokedb --all --no-cache
```

## Configuration

PokéDB includes validated defaults and does not require a configuration file. Settings are selected in this order:

1. `--config path/to/config.json`
2. The `POKEDB_CONFIG` environment variable
3. Packaged defaults in `src/pokedb/default_config.json`

Custom files are partial overrides, so they only need values that differ from the defaults:

```json
{
  "max_workers": 4,
  "output_root": "./generated"
}
```

Relative paths in a custom file are resolved relative to that file. Without a custom file, default paths are resolved relative to the current working directory.

| Setting | Default | Description |
| --- | --- | --- |
| `api_base_url` | `https://pokeapi.co/api/v2/` | PokéAPI base URL; must be HTTP(S) and end in `/`. |
| `timeout` | `15` | Request timeout in seconds. |
| `max_retries` | `3` | Maximum HTTP retry count. |
| `max_workers` | `10` | Parser worker-thread count. |
| `parser_cache_dir` | `./.cache/parser` | API cache directory, or `null` to disable it. |
| `scraper_cache_dir` | `./.cache/scraper` | Scraper cache directory, or `null` to disable it. |
| `cache_expires` | `3600` | Cache lifetime in seconds, or `null` to keep entries indefinitely. |
| `output_root` | `./.output` | Root containing generated `gen1`, `gen2`, and other generation directories. |

`--no-cache` disables both caches for the current run without changing the configuration file.

Older complete configurations containing every `output_dir_*` setting remain supported and are converted to `output_root` when loaded. New configurations should use `output_root`.

Python callers should import `Config` and `load_config` from `pokedb` or `pokedb.config`. The previous `pokedb.utils.config` import path remains available for compatibility.

## Documentation

See the [project wiki](https://github.com/zhenga8533/pokedb/wiki) for data structures and API usage.

## Data contract and validation

Each generation is written below `output_root/genN`. Its `index.json` contains
generation metadata, resource summaries, and counts; individual resource files live
in the corresponding `ability`, `item`, `move`, or `pokemon` subdirectory.

Generated data is validated before the staging tree is published. Validation checks:

- index counts, unique names, and exact agreement between summaries and files;
- required scalar and collection types for each resource;
- version-group maps for generation-specific ability and move fields;
- Pokémon stat names and ranges, type counts, ability and EV entries, learnsets,
  and references to generated abilities when ability data is present.

Identifiers originating in PokéAPI retain their canonical kebab-case spelling, such
as `scarlet-violet` and `special-attack`. Structural field names remain snake_case.
Ability `effect` and `short_effect` are always objects keyed by every version group
in the generated generation, with string or `null` values. This keeps their types
stable even when an ability has no historical changes.

Evolution conditions are reconstructed for the target generation instead of copying
every historical condition from PokéAPI. Each condition includes
`introduced_in_version_group` and the target `version_groups` for which it was
selected. This means, for example, Gen 9 Glaceon uses the Ice Stone condition rather
than retaining the obsolete Ice Rock locations from Generations 4–7.

For historical Pokémon data, structured PokéAPI `past_types`, `past_abilities`, and
`past_stats` are applied first. Pokémon DB's changes section supplements fields that
PokéAPI does not track. Generation 1 uses its original single `special` stat, and
abilities and modern EV yields are empty before Generation 3.

Pokémon DB occasionally describes a change for one game rather than an entire
generation (for example, Pikachu's friendship in Pokémon Yellow). The current output
model does not flatten such a game-specific exception into a generation-wide scalar.
The scraper records these lines as `unsupported_changes` in its cache and emits a
warning instead of silently mistranslating them.

Outputs generated before this data-contract validation was introduced may contain
underscore-normalized identifier keys or stale form-specific fields. Regenerate them
with `python -m pokedb --all --gen <generation> --force` rather than mixing old and
new resource files in a partial run.

Python callers can validate an existing generation explicitly:

```python
from pathlib import Path

from pokedb import validate_generation_output

validate_generation_output(Path(".output/gen9"))
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
