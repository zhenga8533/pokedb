import argparse
import json
import os
from datetime import datetime, timezone

from src.pokeapi_parser.parsers.ability import AbilityParser
from src.pokeapi_parser.parsers.item import ItemParser
from src.pokeapi_parser.parsers.move import MoveParser
from src.pokeapi_parser.parsers.pokemon import PokemonParser
from src.pokeapi_parser.utils import get_latest_generation, load_config, setup_session


def main():
    """Main entry point to run the specified parsers."""
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
    args = parser.parse_args()

    # If no specific parsers are listed and --all is not used, show help.
    if not args.parsers and not args.all:
        parser.print_help()
        return

    config = load_config()
    session = setup_session(config)

    latest_gen_num = get_latest_generation(session, config)
    # If --gen is used, we parse up to that gen. Otherwise, just the latest.
    target_gen = args.gen if args.gen and args.gen <= latest_gen_num else latest_gen_num

    # --- Part 1: Data Gathering Loop ---
    print(f"Gathering all data up to Generation {target_gen}...")
    cumulative_abilities = []
    cumulative_moves = []
    cumulative_pokemon_species = []
    generation_version_groups = {}

    for gen_num in range(1, target_gen + 1):
        try:
            gen_data_url = f"{config['api_base_url']}generation/{gen_num}"
            response = session.get(gen_data_url, timeout=config["timeout"])
            response.raise_for_status()
            gen_data = response.json()

            cumulative_abilities.extend(gen_data.get("abilities", []))
            cumulative_moves.extend(gen_data.get("moves", []))
            cumulative_pokemon_species.extend(gen_data.get("pokemon_species", []))
            generation_version_groups[gen_num] = [vg["name"] for vg in gen_data.get("version_groups", [])]
        except Exception as e:
            print(f"Warning: Could not fetch data for Generation {gen_num}. Error: {e}")

    print("Finished gathering data")

    # --- Part 2: Parsing and Saving (Runs only ONCE) ---
    print(f"\n{'='*10} PARSING ALL DATA FOR GENERATION {target_gen} {'='*10}")

    # Update config paths for the target generation
    final_config = config.copy()
    for key in final_config:
        if key.startswith("output_dir_"):
            final_config[key] = final_config[key].format(gen_num=target_gen)

    all_summaries = {}

    # Run the efficient parsers
    parser_map = {
        "abilities": (
            AbilityParser(final_config, session, generation_version_groups, target_gen),
            cumulative_abilities,
        ),
        "moves": (MoveParser(final_config, session, generation_version_groups, target_gen), cumulative_moves),
        "pokemon_species": (
            PokemonParser(final_config, session, generation_version_groups, target_gen),
            cumulative_pokemon_species,
        ),
    }
    for api_key, (parser_instance, item_list) in parser_map.items():
        parser_name = parser_instance.item_name.lower()
        if args.all or parser_name in args.parsers:
            summary_data = parser_instance.run(item_list)
            if summary_data:
                all_summaries[parser_name] = summary_data
            print("-" * 20)

    # Run the special Item parser if requested
    if args.all or "item" in args.parsers:
        item_master_list_url = f"{config['api_base_url']}item?limit=3000"
        response = session.get(item_master_list_url, timeout=config["timeout"])
        all_items = response.json()["results"]

        item_parser = ItemParser(final_config, session, generation_version_groups, target_gen)
        summary_data = item_parser.run(all_items)
        if summary_data:
            all_summaries["item"] = summary_data
        print("-" * 20)

    # Write the single index.json file for the target generation
    if all_summaries:
        print(f"Creating top-level index.json for Generation {target_gen}...")

        # Build the final index object with metadata
        final_index = {
            "metadata": {
                "generation": target_gen,
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "counts": {key: len(value) for key, value in all_summaries.items()},
            }
        }
        final_index.update(all_summaries)

        top_level_path = os.path.dirname(final_config["output_dir_ability"])
        os.makedirs(top_level_path, exist_ok=True)
        index_file_path = os.path.join(top_level_path, "index.json")

        with open(index_file_path, "w", encoding="utf-8") as f:
            json.dump(final_index, f, indent=4, ensure_ascii=False)
        print(f"Top-level index.json created successfully at '{index_file_path}'")


if __name__ == "__main__":
    main()
