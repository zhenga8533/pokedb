from dotenv import load_dotenv
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import glob
import logging
import json
import os


def parse_growth_rate(num: int, logger: Logger) -> dict:
    url = f"https://pokeapi.co/api/v2/growth-rate/{num}"
    data = request_data(url)
    if data is None:
        return data
    growth_rate = data["name"]
    species = data["pokemon_species"]

    for pokemon in species:
        name = pokemon["name"]
        file_pattern = f"data/pokemon/{name}.json"
        files = glob.glob(file_pattern)

        for file_path in files:
            pokemon = json.loads(load(file_path, logger))
            pokemon["growth_rate"] = growth_rate
            save(file_path, json.dumps(pokemon, indent=4), logger)

    return data


def main():
    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))

    logger = Logger("main", "logs/growth_rate_parser.log", LOG)
    for i in range(STARTING_INDEX, ENDING_INDEX + 1):
        logger.log(logging.INFO, f"Searching for Growth Rate #{i}...")
        growth_rate = parse_growth_rate(i, logger)
        if growth_rate is None:
            logger.log(logging.ERROR, f"Growth Rate #{i} was not found.")
            break
        logger.log(logging.INFO, f"Growth Rate '{growth_rate["name"]}' was parsed successfully.")


if __name__ == "__main__":
    main()
