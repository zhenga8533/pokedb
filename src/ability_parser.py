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


def process_ability_result(result: dict, session: Session, timeout: int, logger: object, max_generation: int) -> None:
    """
    Processes an ability result by fetching its data from the API, checking the generation,
    and saving the processed JSON.

    :param result: The ability result from the API.
    :param session: The shared session to use for requests.
    :param timeout: The timeout for requests.
    :param logger: The logger to use.
    :param max_generation: The maximum generation to process.
    :return: None
    """

    url = result["url"]
    name = result["name"]
    logger.log(logging.INFO, f"Processing ability: {name} from {url}")

    # Fetch data using the shared session.
    try:
        response = session.get(url, timeout=timeout)
    except Exception as e:
        logger.log(logging.ERROR, f"Request failed for {url}: {e}")
        return

    if response.status_code != 200:
        logger.log(logging.ERROR, f"Failed to request {url}: {response.status_code}")
        return

    data = response.json()

    # Check the generation (assumes the name is like "generation-i")
    generation = roman_to_int(data["generation"]["name"].split("-")[1])
    if generation > max_generation:
        logger.log(logging.INFO, f"Skipping ability {name} due to generation {generation}.")
        return

    # Process and save the data.
    ability = {
        "name": data["name"],
        "generation": data["generation"]["name"],
        "pokemon": {
            p["pokemon"]["name"]: {
                "is_hidden": p["is_hidden"],
                "slot": p["slot"],
            }
            for p in data["pokemon"]
        },
        "effect": "",
        "short_effect": "",
        "effect_changes": {},
        "flavor_text_entries": {},
    }

    effect_entry = next((entry for entry in data["effect_entries"] if entry["language"]["name"] == "en"), None)
    if effect_entry:
        ability["effect"] = effect_entry["effect"]
        ability["short_effect"] = effect_entry["short_effect"]

    for change in data.get("effect_changes", []):
        effect = next(
            (entry for entry in change["effect_entries"] if entry["language"]["name"] == "en"), {"effect": ""}
        )["effect"]
        ability["effect_changes"][change["version_group"]["name"]] = effect

    ability["flavor_text_entries"] = {
        entry["version_group"]["name"]: entry["flavor_text"]
        for entry in data.get("flavor_text_entries", [])
        if entry["language"]["name"] == "en"
    }

    json_dump = json.dumps(ability, indent=4)
    save(f"data/abilities/{name}.json", json_dump, logger)
    save(f"generations/gen-{max_generation}/abilities/{name}.json", json_dump, logger)
    logger.log(logging.INFO, f"Successfully processed ability {name}.")


def main():
    """
    Main entry point for the ability parser script.

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

    logger = Logger("Ability Parser", "logs/ability_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Clean and create directories as needed.
    if os.path.exists("data/abilities"):
        shutil.rmtree("data/abilities")
    os.makedirs("data/abilities")

    # Build API URL and fetch results.
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/ability/?offset={offset}&limit={limit}"

    # For initial API call you could use the session from a temporary manager or directly requests.
    tm = ThreadingManager(threads=THREADS, timeout=TIMEOUT, logger=logger)
    response = tm.session.get(api_url, timeout=TIMEOUT)
    if response.status_code != 200:
        logger.log(logging.ERROR, f"Failed to fetch results: {response.status_code}")
        return
    results = response.json().get("results", [])
    logger.log(logging.INFO, "Successfully fetched results data from the API.")

    # Add the results to the queue and run workers.
    tm.add_to_queue(results)
    tm.run_workers(
        lambda result, session, timeout, logger: process_ability_result(
            result, session, timeout, logger, MAX_GENERATION
        )
    )


if __name__ == "__main__":
    main()
