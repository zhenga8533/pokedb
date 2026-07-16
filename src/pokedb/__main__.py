"""Command-line entry point for PokéDB data collection."""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .api_client import ApiClient
from .config import Config, load_config
from .output import (
    PARSER_OUTPUT_KEYS,
    PARSER_SUMMARY_KEYS,
    build_staging_config,
    publish_staged_output,
    write_index_file,
)
from .runner import gather_initial_data, run_parsers
from .validation import validate_generation_output
from .utils import (
    ConfigurationError,
    GenerationNotFoundError,
    PokemonDBError,
    get_latest_generation,
)

logger = logging.getLogger(__name__)


def _parse_generation(value: str) -> Union[int, str]:
    """Parses a positive generation number or the special value 'all'."""
    if value.lower() == "all":
        return "all"
    try:
        generation = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "generation must be a positive integer or 'all'"
        ) from error
    if generation < 1:
        raise argparse.ArgumentTypeError("generation must be at least 1")
    return generation


def parse_arguments() -> argparse.Namespace:
    """Parses and validates command-line arguments."""
    parser = argparse.ArgumentParser(
        description="PokéDB - Parse Pokémon data with historical accuracy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m pokedb --all
  python -m pokedb ability move item
  python -m pokedb --all --gen 3
  python -m pokedb --all --gen all
  python -m pokedb --all --no-cache
  python -m pokedb --all --force
        """,
    )
    parser.add_argument(
        "parsers",
        nargs="*",
        choices=tuple(PARSER_OUTPUT_KEYS),
        help="Parser(s) to run: ability, item, move, or pokemon.",
    )
    parser.add_argument("--all", action="store_true", help="Run every parser.")
    parser.add_argument(
        "--gen",
        type=_parse_generation,
        help="Generation number to parse, or 'all'.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching for this run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing output without confirmation.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Custom JSON configuration path (or set POKEDB_CONFIG).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args()
    if not args.parsers and not args.all:
        parser.error("specify at least one parser or use --all")
    return args


def _requested_parser_names(args: argparse.Namespace) -> set[str]:
    return set(PARSER_OUTPUT_KEYS if args.all else args.parsers)


def _confirm_replacement(args: argparse.Namespace, target_generation: int) -> bool:
    if args.force:
        return True
    response = input(
        f"Output for Generation {target_generation} already exists. "
        "Replace the requested data? (y/n): "
    )
    return response.lower() == "y"


def _load_existing_index(
    staging_output_dir: Path, preserve_existing: bool
) -> Optional[Dict[str, Any]]:
    index_path = staging_output_dir / "index.json"
    if not preserve_existing or not index_path.exists():
        return None
    with index_path.open("r", encoding="utf-8") as index_file:
        return json.load(index_file)


def _prepare_staging_tree(
    final_output_dir: Path, staging_output_dir: Path, preserve_existing: bool
) -> None:
    if staging_output_dir.exists():
        shutil.rmtree(staging_output_dir)
    if final_output_dir.exists() and preserve_existing:
        shutil.copytree(final_output_dir, staging_output_dir)
    else:
        staging_output_dir.mkdir(parents=True)


def _clear_requested_outputs(
    staging_config: Config,
    staging_output_dir: Path,
    requested_parsers: set[str],
) -> None:
    for parser_name in requested_parsers:
        for output_key in PARSER_OUTPUT_KEYS[parser_name]:
            parser_output_dir = staging_config.output_path(output_key)
            if parser_output_dir == staging_output_dir:
                raise ConfigurationError(
                    f"{output_key} cannot point to the generation root"
                )
            if parser_output_dir.exists():
                shutil.rmtree(parser_output_dir)


def _process_generation(
    args: argparse.Namespace,
    config: Config,
    api_client: ApiClient,
    target_generation: int,
    latest_generation: int,
) -> None:
    is_historical = target_generation < latest_generation
    if is_historical:
        logger.info(
            "Performing a historical parse for Generation %s.", target_generation
        )

    version_groups, dex_map, target_versions = gather_initial_data(
        api_client, config, target_generation
    )
    requested_parsers = _requested_parser_names(args)
    logger.info(
        "Parsing %s for Generation %s",
        ", ".join(sorted(requested_parsers)),
        target_generation,
    )

    final_config = config.for_generation(target_generation)
    final_output_dir = final_config.generation_output_root
    if final_output_dir.exists() and not _confirm_replacement(args, target_generation):
        logger.info("Operation cancelled.")
        return

    preserve_existing = final_output_dir.exists() and not args.all
    staging_output_dir = final_output_dir.with_name(
        f".{final_output_dir.name}.staging"
    )
    _prepare_staging_tree(
        final_output_dir, staging_output_dir, preserve_existing
    )

    try:
        staging_config = build_staging_config(final_config, staging_output_dir)
        _clear_requested_outputs(
            staging_config, staging_output_dir, requested_parsers
        )
        existing_index = _load_existing_index(
            staging_output_dir, preserve_existing
        )
        summaries = run_parsers(
            args,
            staging_config,
            api_client,
            version_groups,
            target_generation,
            dex_map,
            is_historical,
            target_versions,
        )
        replaced_keys = {
            summary_key
            for parser_name in requested_parsers
            for summary_key in PARSER_SUMMARY_KEYS[parser_name]
        }
        write_index_file(
            summaries,
            target_generation,
            staging_output_dir,
            version_groups,
            existing_index=existing_index,
            replaced_keys=replaced_keys,
        )
        validate_generation_output(staging_output_dir)
        publish_staged_output(staging_output_dir, final_output_dir)
    finally:
        if staging_output_dir.exists():
            shutil.rmtree(staging_output_dir)


def main() -> None:
    """Runs the requested parsers and publishes complete generation output."""
    try:
        args = parse_arguments()
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format="%(levelname)s: %(message)s",
        )
        config = load_config(args.config)
        if args.no_cache:
            config = config.without_cache()

        api_client = ApiClient(config)
        latest_generation = get_latest_generation(api_client, config)
        if args.gen == "all":
            generations = range(1, latest_generation + 1)
        else:
            target_generation = (
                args.gen if isinstance(args.gen, int) else latest_generation
            )
            if target_generation > latest_generation:
                raise GenerationNotFoundError(
                    f"Generation {target_generation} is newer than the latest "
                    f"available generation ({latest_generation})."
                )
            generations = (target_generation,)

        for target_generation in generations:
            _process_generation(
                args,
                config,
                api_client,
                target_generation,
                latest_generation,
            )
    except PokemonDBError as error:
        logger.error("Fatal error: %s", error)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("Operation cancelled by user")
        sys.exit(130)
    except Exception as error:
        logger.exception("Unexpected error: %s", error)
        sys.exit(1)


if __name__ == "__main__":
    main()
