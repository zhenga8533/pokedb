from dotenv import load_dotenv
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import glob
import logging
import json
import os


def parse_evolution(num: int, logger: Logger, timeout: int) -> dict:
    """
    Parse the data of an evolution chain from the PokeAPI.

    :param num: The number of the evolution chain.
    :param logger: The logger to log messages.
    :param timeout: The timeout of the request.
    :return: The data of the evolution chain.
    """

    url = f"https://pokeapi.co/api/v2/evolution-chain/{num}"
    data = request_data(url, timeout)
    if data is None:
        return data

    pokemon = []

    def parse_evolution_line(chain: dict) -> dict:
        """
        Use recursion to parse the evolution chain.

        :param chain: The evolution chain.
        :return: The parsed evolution chain.
        """

        name = chain["species"]["name"]
        pokemon.append(name)
        evolutions = []

        for evolution in chain["evolves_to"]:
            evolutions.append(parse_evolution_line(evolution))

        return {"name": name, "evolution_details": chain["evolution_details"], "evolutions": evolutions}

    evolutions = [parse_evolution_line(data["chain"])]
    for species in pokemon:
        # Find all files matching the pattern
        file_pattern = f"data/pokemon/{species}*.json"
        files = glob.glob(file_pattern)

        # Process each file
        for file_path in files:
            pokemon = json.loads(load(file_path, logger))
            pokemon["evolutions"] = evolutions
            save(file_path, json.dumps(pokemon, indent=4), logger)

    return data


def main():
    """
    Parse the data of evolution chains from the PokeAPI.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))

    logger = Logger("main", "logs/evolution_parser.log", LOG)
    for i in range(STARTING_INDEX, ENDING_INDEX + 1):
        logger.log(logging.INFO, f"Searching for Evolution #{i}...")
        if parse_evolution(i, logger, TIMEOUT) is None:
            logger.log(logging.ERROR, f"Evolution #{i} was not found.")
            break
        logger.log(logging.INFO, f"Evolution #{i} was parsed successfully.")


if __name__ == "__main__":
    main()
