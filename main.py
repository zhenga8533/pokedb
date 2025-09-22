import argparse

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
    args = parser.parse_args()

    config = load_config()
    session = setup_session(config)
    latest_gen_num = get_latest_generation(session, config)
    for key in config:
        if key.startswith("output_dir_"):
            config[key] = config[key].format(gen_num=latest_gen_num)

    # Map names to class instances
    available_parsers = {
        "ability": AbilityParser(config, session),
        "item": ItemParser(config, session),
        "move": MoveParser(config, session),
        "pokemon": PokemonParser(config, session),
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
        print("No valid parsers specified.")
        return

    if parsers_to_run:
        for parser_instance in parsers_to_run:
            parser_instance.run()
            print("-" * 20)


if __name__ == "__main__":
    main()
