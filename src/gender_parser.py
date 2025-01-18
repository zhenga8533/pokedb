from dotenv import load_dotenv
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import glob
import logging
import json
import os


def parse_gender(num: int, logger: Logger) -> dict:
    url = f"https://pokeapi.co/api/v2/gender/{num}"
    data = request_data(url)
    if data is None:
        return data
    details = data["pokemon_species_details"]

    for detail in details:
        name = detail["pokemon_species"]["name"]
        file_pattern = f"data/pokemon/{name}.json"
        files = glob.glob(file_pattern)

        for file_path in files:
            pokemon = json.loads(load(file_path, logger))
            pokemon["female_rate"] = detail["rate"]
            save(file_path, json.dumps(pokemon, indent=4), logger)

    return data


def main():
    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))

    logger = Logger("main", "logs/gender_parser.log", LOG)
    for i in range(STARTING_INDEX, ENDING_INDEX + 1):
        logger.log(logging.INFO, f"Searching for Gender #{i}...")
        gender = parse_gender(i, logger)
        if gender is None:
            logger.log(logging.ERROR, f"Gender #{i} was not found.")
            break
        logger.log(logging.INFO, f"Gender '{gender["name"]}' was parsed successfully.")


if __name__ == "__main__":
    main()
