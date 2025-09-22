import argparse

from src.pokeapi_parser.parsers import ability, item, move, pokemon
from src.pokeapi_parser.utils import get_latest_generation, git_push_data, load_config, setup_session


def main():
    """Main entry point to run the specified parsers."""
    parser = argparse.ArgumentParser(description="Run parsers for the PokéAPI.")
    parser.add_argument(
        "parsers", nargs="*", help="The name(s) of the parser to run (e.g., ability, item, move, pokemon)."
    )
    parser.add_argument("--all", action="store_true", help="Run all available parsers.")
    parser.add_argument("--push", action="store_true", help="Push the data folder to the data branch after parsing.")
    args = parser.parse_args()

    config = load_config()
    session = setup_session(config)

    latest_gen_num = get_latest_generation(session, config)

    for key in config:
        if key.startswith("output_dir_"):
            config[key] = config[key].format(gen_num=latest_gen_num)

    available_parsers = {
        "ability": ability.main,
        "item": item.main,
        "move": move.main,
        "pokemon": pokemon.main,
    }

    parsers_to_run = []
    if args.all:
        parsers_to_run = list(available_parsers.values())
    else:
        for parser_name in args.parsers:
            if parser_name in available_parsers:
                parsers_to_run.append(available_parsers[parser_name])
            else:
                print(f"Warning: Parser '{parser_name}' not found. Skipping.")

    if not parsers_to_run:
        print("No valid parsers specified. Use --all or provide a name (e.g., ability, item, move, pokemon).")
        return

    if parsers_to_run:
        for run_parser_func in parsers_to_run:
            run_parser_func(config, session)
            print("-" * 20)

    if args.push:
        git_push_data()


if __name__ == "__main__":
    main()
