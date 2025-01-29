from dotenv import load_dotenv
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import glob
import logging
import json
import os
import threading


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


def parse_evolution_range(start_index: int, end_index: int, logger: Logger, timeout: int):
    """
    Parse evolution chains for a range of numbers.

    :param start_index: The starting evolution chain number.
    :param end_index: The ending evolution chain number.
    :param logger: Logger instance for logging.
    :param timeout: The timeout for requests.
    """
    for i in range(start_index, end_index + 1):
        logger.log(logging.INFO, f"Searching for Evolution #{i}...")
        if parse_evolution(i, logger, timeout) is None:
            logger.log(logging.ERROR, f"Evolution #{i} was not found.")
        logger.log(logging.INFO, f"Evolution #{i} was parsed successfully.")


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
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/evolution_parser.log", LOG)

    # Calculate the range each thread will handle
    total_evolution_chains = ENDING_INDEX - STARTING_INDEX + 1
    chunk_size = total_evolution_chains // THREADS
    remainder = total_evolution_chains % THREADS

    threads = []
    start_index = STARTING_INDEX

    for t in range(THREADS):
        # Calculate the end index for each thread's range
        end_index = start_index + chunk_size - 1
        if remainder > 0:
            end_index += 1
            remainder -= 1

        # Start each thread to handle a specific range of evolution chain numbers
        thread = threading.Thread(target=parse_evolution_range, args=(start_index, end_index, logger, TIMEOUT))
        threads.append(thread)
        thread.start()

        # Update the start_index for the next thread
        start_index = end_index + 1

    # Ensure all threads are completed
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
