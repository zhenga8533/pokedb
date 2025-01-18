from dotenv import load_dotenv
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import glob
import logging
import json
import os


def parse_egg_group(num: int, logger: Logger) -> dict:
    url = f"https://pokeapi.co/api/v2/egg-group/{num}"
    data = request_data(url)
    if data is None:
        return data

    egg_group = data["name"]
    species = data["pokemon_species"]

    for pokemon in species:
        name = pokemon["name"]
        file_pattern = f"data/pokemon/{name}.json"
        files = glob.glob(file_pattern)

        for file_path in files:
            pokemon = json.loads(load(file_path, logger))
            pokemon["egg_group"] = egg_group
            save(file_path, json.dumps(pokemon, indent=4), logger)

    return data


def main():
    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))

    logger = Logger("main", "logs/egg_group_parser.log", LOG)
    for i in range(STARTING_INDEX, ENDING_INDEX + 1):
        logger.log(logging.INFO, f"Searching for Egg Group #{i}...")
        egg_group = parse_egg_group(i, logger)
        if egg_group is None:
            logger.log(logging.ERROR, f"Egg Group #{i} was not found.")
            break
        logger.log(logging.INFO, f"Egg Group '{egg_group["name"]}' was parsed successfully.")


if __name__ == "__main__":
    main()
