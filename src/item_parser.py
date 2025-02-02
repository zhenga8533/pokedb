from dotenv import load_dotenv
from queue import Queue, Empty
from util.data import request_data
from util.file import save
from util.logger import Logger
import json
import logging
import os
import threading
import time


# Global dictionary to store the number of threads processing each result.
thread_counts = {}
counter_lock = threading.Lock()


def parse_item(url: str, timeout: int, stop_event: threading.Event, logger: Logger) -> dict:
    """
    Parse the data of an item from the PokeAPI.

    :param url: The URL of the item.
    :param timeout: The timeout of the request.
    :param stop_event: The event to signal when the worker should stop.
    :param logger: The logger to log messages.
    :return: The data of the item.
    """

    # Fetch the data from the API.
    data = request_data(url, timeout, stop_event, logger)
    if data is None:
        return data

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
        fling_effect = request_data(fling_effect["url"], timeout, stop_event, logger)
        if fling_effect is not None:
            effect_entries = fling_effect["effect_entries"]
            fling_effect = next((entry for entry in effect_entries if entry["language"]["name"] == "en"), None)
    item["fling_effect"] = "" if fling_effect is None else fling_effect["effect"]

    return item


def worker(q: Queue, thread_id: int, timeout: int, stop_event: threading.Event, logger: Logger):
    """
    Worker function that continually processes results from the queue.

    :param q: The queue to retrieve results from.
    :param thread_id: The ID of the thread.
    :param timeout: The timeout for the request.
    :param stop_event: The event to signal when the worker should stop.
    :param logger: The logger to log messages.
    :return: None
    """

    process_count = 0

    while not stop_event.is_set():
        # Attempt to retrieve a result from the queue.
        try:
            result = q.get(timeout=0.5)
            name = result["name"]
            url = result["url"]
        except Empty:
            # No more results in the queue: exit the loop.
            break

        # Process and save the result data.
        logger.log(logging.INFO, f'Thread {thread_id} processing "{name}" from "{url}".')
        data = parse_item(url, timeout, stop_event, logger)
        if data is None:
            logger.log(logging.ERROR, f'Failed to parse result "{name}" from "{url}".')
        else:
            logger.log(logging.INFO, f'Succesfully parsed result "{name}" from "{url}".')
            save(f"data/items/{name}.json", json.dumps(data, indent=4), logger)

        # Indicate that the retrieved result has been processed.
        process_count += 1
        q.task_done()

    # Log the thread's exit and update the thread count.
    logger.log(logging.INFO, f"Thread {thread_id} exiting. Processed {process_count} results.")
    with counter_lock:
        thread_counts[thread_id] = process_count


def main():
    """
    Main function to parse results from the PokeAPI using multiple threads.

    :return: None
    """

    # Load environment variables and create logger instance.
    load_dotenv()
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    LOG = os.getenv("LOG") == "True"
    logger = Logger("Item Parser", "logs/item_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Build the API URL and fetch results.
    stop_event = threading.Event()
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/item/?offset={offset}&limit={limit}"
    response = request_data(api_url, TIMEOUT, stop_event, logger)
    if response is None or "results" not in response:
        logger.log(logging.ERROR, "Failed to fetch results data from the API.")
        return

    results = response["results"]
    logger.log(logging.INFO, "Successfully fetched results data from the API.")

    # Create a thread-safe queue and populate it with the results.
    q = Queue()
    for result in results:
        q.put(result)

    # Initialize worker threads
    threads = []
    for i in range(THREADS):
        t = threading.Thread(target=worker, args=(q, i + 1, TIMEOUT, stop_event, logger))
        t.start()
        threads.append(t)

    # Use a polling loop to wait until all threads have completed.
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        # If an interrupt (Ctrl+C) occurs, signal all threads to stop.
        logger.log(logging.WARNING, "Received keyboard interrupt. Stopping all threads.")
        stop_event.set()
    finally:
        # Ensure that every thread has finished execution.
        for t in threads:
            t.join()
        logger.log(logging.INFO, "All threads have exited successfully.")

        # Log the work summary.
        logger.log(logging.INFO, "Work Summary:")
        for i in range(THREADS):
            tid = i + 1
            count = thread_counts.get(tid, 0)
            logger.log(logging.INFO, f"Thread {tid} processed {count} results.")
        total = sum(thread_counts.values())
        logger.log(logging.INFO, f"Total results processed: {total}.")


if __name__ == "__main__":
    main()
