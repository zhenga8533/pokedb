import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Type

from src.pokeapi_parser.api_client import ApiClient
from src.pokeapi_parser.parsers.ability import AbilityParser
from src.pokeapi_parser.parsers.base import BaseParser
from src.pokeapi_parser.parsers.item import ItemParser
from src.pokeapi_parser.parsers.move import MoveParser
from src.pokeapi_parser.parsers.pokemon import PokemonParser
from src.pokeapi_parser.utils import (
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
    return parser.parse_args()


def gather_initial_data(
    api_client: ApiClient, config: Dict[str, Any], target_gen: int
) -> tuple[Dict[int, List[str]], Dict[int, str]]:
    """Gathers the initial data needed by the parsers."""
    print(f"Gathering all data up to Generation {target_gen}...")
    generation_version_groups: Dict[int, List[str]] = {}
    try:
        gen_data = api_client.get(f"{config['api_base_url']}generation/")
        for gen_ref in gen_data.get("results", []):
            gen_num = int(gen_ref["url"].split("/")[-2])
            if gen_num <= target_gen:
                gen_details = api_client.get(gen_ref["url"])
                generation_version_groups[gen_num] = [vg["name"] for vg in gen_details.get("version_groups", [])]
    except Exception as e:
        print(f"Fatal: Could not fetch generation data. Error: {e}")
        exit(1)

    generation_dex_map = get_generation_dex_map(api_client, config)
    print("Finished gathering data")
    return generation_version_groups, generation_dex_map


def run_parsers(
    args: argparse.Namespace,
    final_config: Dict[str, Any],
    api_client: ApiClient,
    generation_version_groups: Dict[int, List[str]],
    target_gen: int,
    generation_dex_map: Dict[int, str],
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
            parser_instance = ParserClass(
                config=final_config,
                api_client=api_client,
                generation_version_groups=generation_version_groups,
                target_gen=target_gen,
                generation_dex_map=generation_dex_map,
            )
            summary_data = parser_instance.run()
            if isinstance(summary_data, list):
                all_summaries[name] = summary_data
            elif isinstance(summary_data, dict):
                all_summaries.update(summary_data)
            print("-" * 20)

    return all_summaries


def write_index_file(
    all_summaries: Dict[str, List[Dict[str, Any]]], target_gen: int, top_level_output_dir: str
) -> None:
    """Writes the final top-level index.json file."""
    if not all_summaries:
        print("No summary data was generated. Skipping index file.")
        return

    print("Creating top-level index.json...")
    final_index: Dict[str, Any] = {
        "metadata": {
            "generation": target_gen,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "counts": {key: len(value) for key, value in all_summaries.items()},
        }
    }
    final_index.update(all_summaries)
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
    api_client = ApiClient(config)

    latest_gen_num = get_latest_generation(api_client, config)
    target_gen = args.gen if args.gen and args.gen <= latest_gen_num else latest_gen_num

    generation_version_groups, generation_dex_map = gather_initial_data(api_client, config, target_gen)

    print(f"\n{'='*10} PARSING ALL DATA FOR GENERATION {target_gen} {'='*10}")

    final_config = config.copy()
    for key in final_config:
        if key.startswith("output_dir_"):
            final_config[key] = final_config[key].format(gen_num=target_gen)

    top_level_output_dir = os.path.dirname(final_config["output_dir_ability"])
    if os.path.exists(top_level_output_dir):
        print(f"Deleting existing directory: '{top_level_output_dir}'")
        shutil.rmtree(top_level_output_dir)

    all_summaries = run_parsers(
        args, final_config, api_client, generation_version_groups, target_gen, generation_dex_map
    )

    write_index_file(all_summaries, target_gen, top_level_output_dir)


if __name__ == "__main__":
    main()
