"""
PokéDB Main Entry Point

This script orchestrates the parsing process for Pokémon data from PokéAPI
and Pokémon DB, supporting generation-specific data extraction and historical
accuracy through web scraping.
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Type

from pokedb.api_client import ApiClient
from pokedb.parsers import (
    AbilityParser,
    BaseParser,
    ItemParser,
    MoveParser,
    PokemonParser,
)
from pokedb.utils import (
    ConfigurationError,
    GenerationNotFoundError,
    PokedexMappingError,
    get_generation_dex_map,
    get_latest_generation,
    load_config,
)

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    """
    Parses command-line arguments for the PokéDB parser.

    Returns:
        Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="PokéDB - Parse Pokémon data from PokéAPI with historical accuracy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse all data for the latest generation
  python -m pokedb --all

  # Parse specific resources for the latest generation
  python -m pokedb ability move item

  # Parse all data for a specific historical generation
  python -m pokedb --all --gen 3

  # Disable caching for a fresh parse
  python -m pokedb --all --no-cache
        """,
    )
    parser.add_argument(
        "parsers",
        nargs="*",
        help="The name(s) of the parser to run (ability, item, move, pokemon).",
    )
    parser.add_argument("--all", action="store_true", help="Run all available parsers.")
    parser.add_argument(
        "--gen",
        type=int,
        help="Parse data for a specific generation (e.g., 3 for Generation III).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching for the run (slower but ensures fresh data).",
    )
    return parser.parse_args()


def gather_initial_data(
    api_client: ApiClient, config: Dict[str, Any], target_gen: int
) -> Tuple[Dict[int, List[str]], Dict[int, str], Set[str]]:
    """
    Gathers the initial data needed by the parsers.

    This includes version groups per generation, version names, and Pokédex mappings.

    Args:
        api_client: The API client instance
        config: Configuration dictionary
        target_gen: The target generation number

    Returns:
        A tuple of (generation_version_groups, generation_dex_map, target_versions)

    Raises:
        GenerationNotFoundError: If generation data cannot be retrieved
        PokedexMappingError: If Pokédex mapping fails
    """
    logger.info(f"Gathering all data up to Generation {target_gen}...")
    generation_version_groups: Dict[int, List[str]] = {}
    target_versions: Set[str] = set()

    try:
        gen_data = api_client.get(f"{config['api_base_url']}generation/")

        for gen_ref in gen_data.get("results", []):
            gen_num = int(gen_ref["url"].split("/")[-2])

            if gen_num <= target_gen:
                gen_details = api_client.get(gen_ref["url"])
                version_groups = [
                    vg["name"] for vg in gen_details.get("version_groups", [])
                ]
                generation_version_groups[gen_num] = version_groups

                # Only collect versions from the target generation
                if gen_num == target_gen:
                    for version_group_name in version_groups:
                        version_group_url = f"{config['api_base_url']}version-group/{version_group_name}"
                        version_group_data = api_client.get(version_group_url)

                        for version in version_group_data.get("versions", []):
                            target_versions.add(version["name"])

    except Exception as e:
        raise GenerationNotFoundError(f"Could not fetch generation data: {e}")

    generation_dex_map = get_generation_dex_map(api_client, config)
    logger.info("Finished gathering data")
    return generation_version_groups, generation_dex_map, target_versions


def run_parsers(
    args: argparse.Namespace,
    final_config: Dict[str, Any],
    api_client: ApiClient,
    generation_version_groups: Dict[int, List[str]],
    target_gen: int,
    generation_dex_map: Dict[int, str],
    is_historical: bool,
    target_versions: Set[str],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Initializes and runs the requested parsers.

    Args:
        args: Command-line arguments
        final_config: Configuration with formatted output directories
        api_client: The API client instance
        generation_version_groups: Mapping of generations to version groups
        target_gen: The target generation number
        generation_dex_map: Mapping of generations to regional dexes
        is_historical: Whether to scrape historical changes
        target_versions: Set of version names in the target generation

    Returns:
        A dictionary mapping parser names to their summary data lists
    """
    all_summaries: Dict[str, List[Dict[str, Any]]] = {}
    parser_classes: Dict[str, Type[BaseParser]] = {
        "ability": AbilityParser,
        "move": MoveParser,
        "item": ItemParser,
        "pokemon": PokemonParser,
    }

    for parser_name, ParserClass in parser_classes.items():
        if args.all or parser_name in args.parsers:
            parser_kwargs = {
                "config": final_config,
                "api_client": api_client,
                "generation_version_groups": generation_version_groups,
                "target_gen": target_gen,
                "generation_dex_map": generation_dex_map,
            }

            # Pokemon parser requires additional parameters
            if parser_name == "pokemon":
                parser_kwargs["is_historical"] = is_historical
                parser_kwargs["target_versions"] = target_versions

            parser_instance = ParserClass(**parser_kwargs)
            summary_data = parser_instance.run()

            if isinstance(summary_data, list):
                all_summaries[parser_name] = summary_data
            elif isinstance(summary_data, dict):
                all_summaries.update(summary_data)

            logger.info("-" * 20)

    return all_summaries


def write_index_file(
    all_summaries: Dict[str, List[Dict[str, Any]]],
    target_gen: int,
    top_level_output_dir: str,
    generation_version_groups: Dict[int, List[str]],
) -> None:
    """
    Writes the final top-level index.json file.

    This index contains metadata and summary information for all parsed resources.

    Args:
        all_summaries: Dictionary mapping resource types to their summary lists
        target_gen: The target generation number
        top_level_output_dir: The output directory path
        generation_version_groups: Mapping of generations to version groups
    """
    if not all_summaries:
        logger.warning("No summary data was generated. Skipping index file.")
        return

    logger.info("Creating top-level index.json...")

    final_index: Dict[str, Any] = {
        "metadata": {
            "generation": target_gen,
            "version_groups": generation_version_groups.get(target_gen, []),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "counts": {
                key: len(value) for key, value in all_summaries.items() if value
            },
        }
    }
    final_index.update({key: value for key, value in all_summaries.items() if value})

    output_path = Path(top_level_output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    index_file_path = output_path / "index.json"
    with open(index_file_path, "w", encoding="utf-8") as f:
        json.dump(final_index, f, indent=4, ensure_ascii=False)

    logger.info(f"Top-level index.json created successfully at '{index_file_path}'")


def main() -> None:
    """
    Main entry point to run the specified parsers.

    This orchestrates the entire parsing process:
    1. Parses command-line arguments
    2. Loads configuration
    3. Gathers initial generation data
    4. Runs requested parsers concurrently
    5. Writes summary index file
    """
    try:
        args = parse_arguments()
        if not args.parsers and not args.all:
            logger.error(
                "No parsers specified. Use --all to run all parsers or provide a list of parsers."
            )
            return

        # Load and configure
        config = load_config()
        if args.no_cache:
            logger.info("Caching is disabled for this run.")
            config["parser_cache_dir"] = None
            config["scraper_cache_dir"] = None
            config["cache_expires"] = None

        api_client = ApiClient(config)

        # Determine target generation
        latest_gen_num = get_latest_generation(api_client, config)
        target_gen = (
            args.gen if args.gen and args.gen <= latest_gen_num else latest_gen_num
        )
        is_historical = target_gen < latest_gen_num

        if is_historical:
            logger.info(
                f"Performing a historical parse for Generation {target_gen}. Scraping for changes..."
            )

        # Gather initial data
        generation_version_groups, generation_dex_map, target_versions = (
            gather_initial_data(api_client, config, target_gen)
        )

        logger.info(f"\n{'='*10} PARSING ALL DATA FOR GENERATION {target_gen} {'='*10}")

        # Format output directory paths with generation number
        final_config = config.copy()
        for key in final_config:
            if key.startswith("output_dir_"):
                final_config[key] = final_config[key].format(gen_num=target_gen)

        # Check if output directory exists
        top_level_output_dir = Path(final_config["output_dir_ability"]).parent
        if top_level_output_dir.exists():
            response = input(
                f"Directory '{top_level_output_dir}' already exists. Delete it? (y/n): "
            )
            if response.lower() == "y":
                logger.info(f"Deleting existing directory: '{top_level_output_dir}'")
                shutil.rmtree(top_level_output_dir)
            else:
                logger.info("Operation cancelled.")
                return

        # Run parsers
        all_summaries = run_parsers(
            args,
            final_config,
            api_client,
            generation_version_groups,
            target_gen,
            generation_dex_map,
            is_historical,
            target_versions,
        )

        # Write index file
        write_index_file(
            all_summaries,
            target_gen,
            str(top_level_output_dir),
            generation_version_groups,
        )

    except (ConfigurationError, GenerationNotFoundError, PokedexMappingError) as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.warning("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
