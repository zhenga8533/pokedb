import glob
import json
import logging
import os

from dotenv import load_dotenv
from requests import Session

from util.data import session_request
from util.file import load, save
from util.logger import Logger
from util.threading import ThreadingManager


def parse_evolution_line(chain: dict, pokemon: list) -> dict:
    """
    Recursively parse an evolution chain.

    :param chain: The chain to parse.
    :param pokemon: The list of Pokémon names to update.
    :return: A dictionary with the parsed evolution data.
    """

    name = chain["species"]["name"]
    pokemon.append(name)
    evolutions = [parse_evolution_line(evolution, pokemon) for evolution in chain["evolves_to"]]
    return {
        "name": name,
        "evolution_details": chain["evolution_details"],
        "evolutions": evolutions,
    }


def parse_evolution(url: str, session: Session, timeout: int, logger: Logger, max_generation: int) -> dict:
    """
    Parse the evolution data from the API using the shared session.

    :param url: The URL of the evolution chain.
    :param session: The requests.Session object.
    :param timeout: The timeout for the request.
    :param logger: The logger instance.
    :param max_generation: The maximum generation to parse.
    :return: A dictionary with the parsed evolution data, or None if unsuccessful.
    """

    response = session_request(session, url, timeout, logger)
    if response is None:
        return None
    data = response.json()

    # Build the evolution chain and collect Pokémon species names.
    pokemon = []
    evolutions = [parse_evolution_line(data["chain"], pokemon)]

    # Update each Pokémon's data file with its evolution information.
    for species in pokemon:
        gen = "generations/gen-" + str(max_generation)
        file_pattern = f"{gen}/pokemon/{species}*.json"
        files = glob.glob(file_pattern)
        for file_path in files:
            file_path = file_path.replace("\\", "/")
            pokemon_data = json.loads(load(file_path, logger))
            pokemon_data["evolutions"] = evolutions
            json_dump = json.dumps(pokemon_data, indent=4)
            save(file_path.replace(gen, "data"), json_dump, logger)
            save(file_path, json_dump, logger)

    return data


def process_evolution_result(
    result: dict, session: Session, timeout: int, logger: Logger, max_generation: int
) -> None:
    """
    Processes an evolution chain result by fetching its data from the API,
    parsing the evolution chain, and updating the corresponding Pokémon files.

    :param result: The evolution chain result from the API.
    :param session: The shared session to use for requests.
    :param timeout: The timeout for requests.
    :param logger: The logger to use.
    :param max_generation: The maximum generation to process.
    :return: None
    """

    url = result["url"]
    logger.log(logging.INFO, f'Processing evolution chain from "{url}".')
    data = parse_evolution(url, session, timeout, logger, max_generation)
    if data is None:
        logger.log(logging.ERROR, f'Failed to parse result "{url}".')
    else:
        logger.log(logging.INFO, f'Successfully parsed result "{url}".')


def main():
    """
    Main entry point for the evolution parser script.

    :return: None
    """

    # Load environment variables and setup logger.
    load_dotenv()
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    MAX_GENERATION = int(os.getenv("MAX_GENERATION"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))
    LOG = os.getenv("LOG") == "True"

    logger = Logger("Evolution Parser", "logs/evolution_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Build the API URL for evolution chains.
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/evolution-chain/?offset={offset}&limit={limit}"

    # Create a ThreadingManager instance (which creates its own session with retry support).
    tm = ThreadingManager(threads=THREADS, timeout=TIMEOUT, logger=logger)

    # Fetch the list of evolution chain results using the shared session.
    response = session_request(tm.session, api_url, TIMEOUT, logger)
    if response is None:
        return None
    results = response.json()["results"]

    # Populate the shared queue with the results.
    tm.add_to_queue(results)
    # Run the worker threads, passing in the evolution processing callback.
    tm.run_workers(
        lambda result, session, timeout, logger: process_evolution_result(
            result, session, timeout, logger, MAX_GENERATION
        )
    )


if __name__ == "__main__":
    main()
