import json
import logging
import os
import shutil

from dotenv import load_dotenv
from requests import Session

from util.file import save
from util.format import roman_to_int
from util.logger import Logger
from util.threading import ThreadingManager


def parse_item(url: str, session: Session, timeout: int, logger: Logger, max_generation: int) -> dict:
    """
    Parse the data of an item from the PokeAPI.

    :param url: The URL of the item.
    :param session: The shared requests session.
    :param timeout: The timeout for the request.
    :param logger: The logger to log messages.
    :param max_generation: The maximum generation to parse.
    :return: The data of the item as a dictionary, or None if unsuccessful.
    """

    try:
        response = session.get(url, timeout=timeout)
    except Exception as e:
        logger.log(logging.ERROR, f"Request failed for {url}: {e}", exc_info=True)
        return None

    if response.status_code != 200:
        logger.log(logging.ERROR, f"Failed to request {url}: {response.status_code}")
        return None

    data = response.json()

    # Check generation (assumes each game index contains a generation name like "generation-i")
    game_indices = [roman_to_int(game["generation"]["name"].split("-")[-1]) for game in data["game_indices"]]
    if not game_indices:
        return None
    lowest_generation = min(game_indices)
    if lowest_generation > max_generation:
        return None

    item = {}
    # General item information.
    item["name"] = data["name"]
    item["cost"] = data["cost"]
    item["category"] = data["category"]["name"]
    item["attributes"] = [attribute["name"] for attribute in data["attributes"]]

    # Item game data.
    item["sprite"] = data["sprites"]["default"]
    item["games"] = [game["generation"]["name"] for game in data["game_indices"]]
    item["held_by"] = {
        pokemon.get("name", "?"): {
            version["version"]["name"]: version["rarity"] for version in pokemon["version_details"]
        }
        for pokemon in data["held_by_pokemon"]
    }

    # Item effect and flavor text entries.
    effect_entry = next((entry for entry in data["effect_entries"] if entry["language"]["name"] == "en"), None)
    item["effect"] = "" if effect_entry is None else effect_entry["effect"]
    item["short_effect"] = "" if effect_entry is None else effect_entry["short_effect"]
    item["flavor_text_entries"] = {
        entry["version_group"]["name"]: entry["text"]
        for entry in data["flavor_text_entries"]
        if entry["language"]["name"] == "en"
    }
    item["fling_power"] = data["fling_power"]

    fling_effect = data["fling_effect"]
    if fling_effect is not None:
        try:
            response2 = session.get(fling_effect["url"], timeout=timeout)
        except Exception as e:
            logger.log(logging.ERROR, f"Request failed for fling effect URL {fling_effect['url']}: {e}", exc_info=True)
            fling_effect = None
        else:
            if response2.status_code != 200:
                logger.log(
                    logging.ERROR, f"Failed to request fling effect URL {fling_effect['url']}: {response2.status_code}"
                )
                fling_effect = None
            else:
                fling_effect_data = response2.json()
                effect_entries = fling_effect_data["effect_entries"]
                fling_effect = next((entry for entry in effect_entries if entry["language"]["name"] == "en"), None)
    item["fling_effect"] = "" if fling_effect is None else fling_effect["effect"]

    return item


def process_item_result(result: dict, session: Session, timeout: int, logger: Logger, max_generation: int):
    """
    Process an item result by parsing its data from the API and saving it.

    :param result: A dictionary containing at least 'name' and 'url' keys.
    :param session: The shared requests session.
    :param timeout: The timeout for each API request.
    :param logger: The logger instance.
    :param max_generation: The maximum generation to parse.
    """

    name = result["name"]
    url = result["url"]
    logger.log(logging.INFO, f'Processing item "{name}" from "{url}".')
    data = parse_item(url, session, timeout, logger, max_generation)
    if data is None:
        logger.log(logging.ERROR, f'Failed to parse item "{name}" from "{url}".')
    else:
        logger.log(logging.INFO, f'Successfully parsed item "{name}" from "{url}".')
        json_dump = json.dumps(data, indent=4)
        save(f"data/items/{name}.json", json_dump, logger)
        save(f"data-bk/items/{name}.min.json", json_dump, logger)


def main():
    """
    Main entry point for the item parser script.

    :return: None
    """

    load_dotenv()
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    MAX_GENERATION = int(os.getenv("MAX_GENERATION"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))
    LOG = os.getenv("LOG") == "True"

    logger = Logger("Item Parser", "logs/item_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Clean and create directories as needed.
    logger.log(logging.INFO, "Deleting existing data directory.")
    if os.path.exists("data/items"):
        shutil.rmtree("data/items")
    logger.log(logging.INFO, "Creating new data directory.")
    os.makedirs("data/items")

    # Build the API URL and fetch results.
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/item/?offset={offset}&limit={limit}"

    # Create a ThreadingManager instance (which creates its own session with retry support).
    tm = ThreadingManager(threads=THREADS, timeout=TIMEOUT, logger=logger)

    try:
        logger.log(logging.INFO, f"Requesting item index data from '{api_url}'.")
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
    # Run worker threads. We pass a lambda so that max_generation is included in the callback.
    tm.run_workers(
        lambda result, session, timeout, logger: process_item_result(result, session, timeout, logger, MAX_GENERATION)
    )


if __name__ == "__main__":
    main()
