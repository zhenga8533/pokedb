import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple, Type

from src.pokedb.api_client import ApiClient
from src.pokedb.parsers.ability import AbilityParser
from src.pokedb.parsers.base import BaseParser
from src.pokedb.parsers.item import ItemParser
from src.pokedb.parsers.move import MoveParser
from src.pokedb.parsers.pokemon import PokemonParser
from src.pokedb.utils import (
    get_generation_dex_map,
    get_latest_generation,
    load_config,
)


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Run parsers for the PokéAPI.")
    parser.add_argument(
        "parsers", nargs="*", help="The name(s) of the parser to run (e.g., ability, item, move, pokemon)."
    )
    parser.add_argument("--all", action="store_true", help="Run all available parsers.")
    parser.add_argument(
        "--gen",
        type=int,
        help="Parse all data up to a specific generation number, outputting only that generation's folder.",
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable caching for the run.")
    return parser.parse_args()


def gather_initial_data(
    api_client: ApiClient, config: Dict[str, Any], target_gen: int
) -> Tuple[Dict[int, List[str]], Dict[int, str], Set[str]]:
    """Gathers the initial data needed by the parsers."""
    print(f"Gathering all data up to Generation {target_gen}...")
    generation_version_groups: Dict[int, List[str]] = {}
    target_versions: Set[str] = set()
    try:
        gen_data = api_client.get(f"{config['api_base_url']}generation/")
        for gen_ref in gen_data.get("results", []):
            gen_num = int(gen_ref["url"].split("/")[-2])
            if gen_num <= target_gen:
                gen_details = api_client.get(gen_ref["url"])
                version_groups = [vg["name"] for vg in gen_details.get("version_groups", [])]
                generation_version_groups[gen_num] = version_groups

                if gen_num == target_gen:
                    for vg_name in version_groups:
                        vg_data = api_client.get(f"{config['api_base_url']}version-group/{vg_name}")
                        for version in vg_data.get("versions", []):
                            target_versions.add(version["name"])

    except Exception as e:
        print(f"Fatal: Could not fetch generation data. Error: {e}")
        exit(1)

    generation_dex_map = get_generation_dex_map(api_client, config)
    print("Finished gathering data")
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
    """Initializes and runs the requested parsers."""
    all_summaries: Dict[str, List[Dict[str, Any]]] = {}
    parser_classes: Dict[str, Type[BaseParser]] = {
        "ability": AbilityParser,
        "move": MoveParser,
        "item": ItemParser,
        "pokemon": PokemonParser,
    }

    for name, ParserClass in parser_classes.items():
        if args.all or name in args.parsers:
            parser_kwargs = {
                "config": final_config,
                "api_client": api_client,
                "generation_version_groups": generation_version_groups,
                "target_gen": target_gen,
                "generation_dex_map": generation_dex_map,
            }
            if name == "pokemon":
                parser_kwargs["is_historical"] = is_historical
                parser_kwargs["target_versions"] = target_versions

            parser_instance = ParserClass(**parser_kwargs)
            summary_data = parser_instance.run()

            if isinstance(summary_data, list):
                all_summaries[name] = summary_data
            elif isinstance(summary_data, dict):
                all_summaries.update(summary_data)
            print("-" * 20)

    return all_summaries


def write_index_file(
    all_summaries: Dict[str, List[Dict[str, Any]]],
    target_gen: int,
    top_level_output_dir: str,
    generation_version_groups: Dict[int, List[str]],
) -> None:
    """Writes the final top-level index.json file."""
    if not all_summaries:
        print("No summary data was generated. Skipping index file.")
        return

    print("Creating top-level index.json...")
    final_index: Dict[str, Any] = {
        "metadata": {
            "generation": target_gen,
            "version_groups": generation_version_groups.get(target_gen, []),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "counts": {key: len(value) for key, value in all_summaries.items() if value},
        }
    }
    final_index.update({key: value for key, value in all_summaries.items() if value})
    index_file_path = os.path.join(top_level_output_dir, "index.json")
    os.makedirs(top_level_output_dir, exist_ok=True)
    with open(index_file_path, "w", encoding="utf-8") as f:
        json.dump(final_index, f, indent=4, ensure_ascii=False)
    print(f"Top-level index.json created successfully at '{index_file_path}'")


def main() -> None:
    """
    Main entry point to run the specified parsers.
    """
    args = parse_arguments()
    if not args.parsers and not args.all:
        print("No parsers specified. Use --all to run all parsers or provide a list of parsers.")
        return

    config = load_config()
    if args.no_cache:
        print("Caching is disabled for this run.")
        config["parser_cache_dir"] = None
        config["scraper_cache_dir"] = None
        config["cache_expires"] = None

    api_client = ApiClient(config)

    latest_gen_num = get_latest_generation(api_client, config)
    target_gen = args.gen if args.gen and args.gen <= latest_gen_num else latest_gen_num
    is_historical = target_gen < latest_gen_num

    if is_historical:
        print(f"Performing a historical parse for Generation {target_gen}. Scraping for changes...")

    generation_version_groups, generation_dex_map, target_versions = gather_initial_data(
        api_client, config, target_gen
    )

    print(f"\n{'='*10} PARSING ALL DATA FOR GENERATION {target_gen} {'='*10}")

    final_config = config.copy()
    for key in final_config:
        if key.startswith("output_dir_"):
            final_config[key] = final_config[key].format(gen_num=target_gen)

    top_level_output_dir = os.path.dirname(final_config["output_dir_ability"])
    if os.path.exists(top_level_output_dir):
        response = input(f"Directory '{top_level_output_dir}' already exists. Delete it? (y/n): ")
        if response.lower() == "y":
            print(f"Deleting existing directory: '{top_level_output_dir}'")
            shutil.rmtree(top_level_output_dir)
        else:
            print("Operation cancelled.")
            sys.exit(0)

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

    write_index_file(all_summaries, target_gen, top_level_output_dir, generation_version_groups)


if __name__ == "__main__":
    main()
