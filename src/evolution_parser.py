import glob
import json
import logging
import os

from dotenv import load_dotenv
from requests import Session

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
    evolutions = [parse_evolution_line(evolution, pokemon) for evolution in chain.get("evolves_to", [])]
    return {
        "name": name,
        "evolution_details": chain["evolution_details"],
        "evolutions": evolutions,
    }


def parse_evolution(url: str, session: Session, timeout: int, logger: Logger) -> dict:
    """
    Parse the evolution data from the API using the shared session.

    :param url: The URL of the evolution chain.
    :param session: The requests.Session object.
    :param timeout: The timeout for the request.
    :param logger: The logger instance.
    :return: A dictionary with the parsed evolution data, or None if unsuccessful.
    """

    try:
        logger.log(logging.INFO, f"Requesting data from '{url}'.")
        response = session.get(url, timeout=timeout)
    except Exception as e:
        logger.log(logging.ERROR, f"Request to '{url}' failed: {e}", exc_info=True)
        return None

    if response.status_code != 200:
        logger.log(logging.ERROR, f"Failed to request data from '{url}': {response.status_code}")
        return None

    data = response.json()

    # Build the evolution chain and collect Pokémon species names.
    pokemon = []
    evolutions = [parse_evolution_line(data["chain"], pokemon)]

    # Update each Pokémon's data file with its evolution information.
    for species in pokemon:
        file_pattern = f"data/pokemon/{species}*.json"
        files = glob.glob(file_pattern)
        for file_path in files:
            pokemon_data = json.loads(load(file_path, logger))
            pokemon_data["evolutions"] = evolutions
            json_dump = json.dumps(pokemon_data, indent=4)
            save(file_path, json_dump, logger)
            # Also save a backup.
            save(file_path.replace("data/", "data-bk/"), json_dump, logger)

    return data


def process_evolution_result(result: dict, session: Session, timeout: int, logger: Logger) -> None:
    """
    Processes an evolution chain result by fetching its data from the API,
    parsing the evolution chain, and updating the corresponding Pokémon files.

    :param result: The evolution chain result from the API.
    :param session: The shared session to use for requests.
    :param timeout: The timeout for requests.
    :param logger: The logger to use.
    :return: None
    """

    url = result["url"]
    logger.log(logging.INFO, f'Processing evolution chain from "{url}".')
    data = parse_evolution(url, session, timeout, logger)
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
    try:
        logger.log(logging.INFO, f"Requesting evolution chain index data from '{api_url}'.")
        response = tm.session.get(api_url, timeout=TIMEOUT)
    except Exception as e:
        logger.log(logging.ERROR, f"Request to '{api_url}' failed: {e}", exc_info=True)
        return

    if response.status_code != 200:
        logger.log(logging.ERROR, f"Failed to fetch results from '{api_url}': {response.status_code}")
        return

    data = response.json()
    results = data.get("results")
    if not results:
        logger.log(logging.ERROR, "No results found in the API response.")
        return

    logger.log(logging.INFO, "Successfully fetched results data from the API.")

    # Populate the shared queue with the results.
    tm.add_to_queue(results)
    # Run the worker threads, passing in the evolution processing callback.
    tm.run_workers(process_evolution_result)


if __name__ == "__main__":
    main()
