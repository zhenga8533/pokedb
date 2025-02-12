import json
import logging
import os
import shutil

from dotenv import load_dotenv
from requests import Session

from util.data import session_request
from util.file import save
from util.format import roman_to_int
from util.logger import Logger
from util.threading import ThreadingManager


def parse_move(url: str, session: Session, timeout: int, logger: Logger, max_generation: int) -> dict:
    """
    Parse the data of a move from the PokeAPI using the shared session.

    :param url: The URL of the move.
    :param session: The shared requests session.
    :param timeout: The timeout for the request.
    :param logger: The logger to log messages.
    :param max_generation: The maximum generation to parse.
    :return: A dictionary with the move data, or None if unsuccessful.
    """

    response = session_request(session, url, timeout, logger)
    if response is None:
        return None
    data = response.json()

    # Check generation (assumes generation name is like "generation-i")
    generation = roman_to_int(data["generation"]["name"].split("-")[1])
    if generation > max_generation:
        return None

    move = {}
    # General move information.
    move["name"] = data["name"]
    move["accuracy"] = data["accuracy"]
    move["damage_class"] = data["damage_class"]["name"]
    move["power"] = data["power"]
    move["pp"] = data["pp"]
    move["priority"] = data["priority"]
    move["target"] = data["target"]["name"]
    move["type"] = data["type"]["name"]

    # Move effects.
    move["effect_chance"] = data["effect_chance"]
    move["effect_changes"] = data["effect_changes"]
    effect_entries = data["effect_entries"]
    if not effect_entries:
        move["effect"] = ""
    else:
        effect_entry = next(entry for entry in effect_entries if entry["language"]["name"] == "en")
        move["effect"] = effect_entry["effect"]
    move["flavor_text_entries"] = {
        entry["version_group"]["name"]: entry["flavor_text"]
        for entry in data["flavor_text_entries"]
        if entry["language"]["name"] == "en"
    }
    move["meta"] = data["meta"]
    move["stat_changes"] = data["stat_changes"]

    # Move learn data.
    move["generation"] = data["generation"]["name"]
    move["learned_by"] = [pokemon["name"] for pokemon in data["learned_by_pokemon"]]
    move["machines"] = {}
    machines = [machine["machine"]["url"] for machine in data["machines"]]
    for machine_url in machines:
        machine_response = session_request(session, machine_url, timeout, logger)
        if machine_response is None:
            return None
        machine_data = machine_response.json()
        machine_name = machine_data["item"]["name"]
        machine_version = machine_data["version_group"]["name"]
        move["machines"][machine_version] = machine_name

    return move


def process_move_result(result: dict, session: Session, timeout: int, logger: Logger, max_generation: int) -> None:
    """
    Process a move result by fetching its data from the API and saving the parsed move data.

    :param result: A dictionary containing at least the 'name' and 'url' of the move.
    :param session: The shared requests session.
    :param timeout: The timeout for each API request.
    :param logger: The logger instance.
    :param max_generation: The maximum generation to parse.
    :return: None
    """

    name = result["name"]
    url = result["url"]
    logger.log(logging.INFO, f'Processing move "{name}" from "{url}".')
    data = parse_move(url, session, timeout, logger, max_generation)
    if data is None:
        logger.log(logging.ERROR, f'Failed to parse move "{name}" from "{url}".')
    else:
        logger.log(logging.INFO, f'Successfully parsed move "{name}" from "{url}".')
        json_dump = json.dumps(data, indent=4)
        save(f"data/moves/{name}.json", json_dump, logger)
        save(f"generations/gen-{max_generation}/moves/{name}.json", json_dump, logger)


def main():
    """
    Main entry point for the move parser script.

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

    logger = Logger("Move Parser", "logs/move_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Delete the existing data directory.
    logger.log(logging.INFO, "Deleting existing data directory.")
    if os.path.exists("data/moves"):
        shutil.rmtree("data/moves")
    logger.log(logging.INFO, "Creating new data directory.")
    os.makedirs("data/moves")

    # Build the API URL and fetch the move index results.
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/move/?offset={offset}&limit={limit}"

    # Create a ThreadingManager instance (which creates its own session with retry support).
    tm = ThreadingManager(threads=THREADS, timeout=TIMEOUT, logger=logger)

    # Fetch the list of move results using the shared session.
    response = session_request(tm.session, api_url, TIMEOUT, logger)
    if response is None:
        return None
    results = response.json()["results"]

    # Populate the shared queue with the results.
    tm.add_to_queue(results)
    # Run worker threads using the ThreadingManager.
    # A lambda is used here to pass MAX_GENERATION into the callback.
    tm.run_workers(
        lambda result, session, timeout, logger: process_move_result(result, session, timeout, logger, MAX_GENERATION)
    )


if __name__ == "__main__":
    main()
