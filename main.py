import argparse

from src.pokeapi_parser.parsers import ability, item


def main():
    """Main entry point to run the specified parsers."""
    parser = argparse.ArgumentParser(description="Run parsers for the PokéAPI.")
    parser.add_argument("parsers", nargs="*", help="The name(s) of the parser to run (e.g., ability).")
    parser.add_argument("--all", action="store_true", help="Run all available parsers.")

    args = parser.parse_args()

    available_parsers = {
        "ability": ability.main,
        "item": item.main,
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
        print("No valid parsers specified. Use --all or provide a name (e.g., ability).")
        return

    for run_parser_func in parsers_to_run:
        run_parser_func()
        print("-" * 20)


if __name__ == "__main__":
    main()
