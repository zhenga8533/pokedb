from dotenv import load_dotenv
from queue import Queue, Empty
from util.data import request_data
from util.file import save
from util.logger import Logger
import json
import logging
import os
import signal
import threading
import time


def parse_item(url: str, timeout: int) -> dict:
    """
    Parse the data of an item from the PokeAPI.

    :param url: The URL of the item.
    :param timeout: The timeout of the request.
    :return: The data of the item.
    """

    data = request_data(url, timeout)
    if data is None:
        return data

    item = {}
    item["name"] = data["name"]
    item["cost"] = data["cost"]
    item["category"] = data["category"]["name"]
    item["sprite"] = data["sprites"]["default"]
    item["games"] = [game["generation"]["name"] for game in data["game_indices"]]
    item["held_by"] = {
        pokemon.get("name", "?"): {
            version["version"]["name"]: version["rarity"] for version in pokemon["version_details"]
        }
        for pokemon in data["held_by_pokemon"]
    }
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
        fling_effect = request_data(fling_effect["url"], timeout)
        if fling_effect is not None:
            effect_entries = fling_effect["effect_entries"]
            fling_effect = next((entry for entry in effect_entries if entry["language"]["name"] == "en"), None)
    item["fling_effect"] = "" if fling_effect is None else fling_effect["effect"]
    item["attributes"] = [attribute["name"] for attribute in data["attributes"]]
    return item


def worker(q: Queue, timeout: int, logger: Logger, stop_event: threading.Event) -> None:
    """
    Worker function to parse items from the queue.

    :param q: The queue of items to parse.
    :param timeout: The timeout of the request.
    :param logger: The logger to log messages.
    :param stop_event: The event to signal the workers to stop.
    :return: None
    """

    while not stop_event.is_set():
        try:
            # Use a timeout so the worker can check the stop_event periodically.
            item = q.get(timeout=1)
        except Empty:
            continue

        if stop_event.is_set():
            q.task_done()
            break

        name = item["name"]
        logger.log(logging.INFO, f"Parsing item {name}...")
        data = parse_item(item["url"], timeout)

        if data is None:
            logger.log(logging.ERROR, f"Failed to parse item {name} from {item['url']}")
            q.task_done()
            continue

        logger.log(logging.INFO, f"Parsed item {name}")
        save(f"data/items/{name}.json", json.dumps(data, indent=4), logger)
        q.task_done()


def main():
    """
    Main function to parse items from the PokeAPI.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/item_parser.log", LOG)

    # Build the API URL and fetch items.
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/item/?offset={offset}&limit={limit}"
    response = request_data(api_url, TIMEOUT)
    if response is None or "results" not in response:
        logger.log(logging.ERROR, "Failed to fetch items from the API.")
        return

    items = response["results"]

    # Populate the queue.
    q = Queue()
    for item in items:
        q.put(item)

    # Create an event to signal the workers to stop.
    stop_event = threading.Event()

    # Start worker threads as daemon threads.
    threads = []
    for _ in range(THREADS):
        thread = threading.Thread(target=worker, args=(q, TIMEOUT, logger, stop_event))
        thread.daemon = True
        thread.start()
        threads.append(thread)

    # Force an immediate shutdown when Ctrl+C is pressed.
    def signal_handler(sig, frame):
        logger.log(logging.INFO, "Received SIGINT, forcing immediate shutdown with os._exit(0)")
        os._exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Poll the worker threads rather than waiting on q.join().
    try:
        while any(thread.is_alive() for thread in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.log(logging.INFO, "KeyboardInterrupt caught in main loop, forcing shutdown with os._exit(0)")
        os._exit(0)

    logger.log(logging.INFO, "Shutdown complete.")


if __name__ == "__main__":
    main()
