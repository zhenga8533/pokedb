from dotenv import load_dotenv
from queue import Queue, Empty
from util.data import request_data
from util.file import save
from util.format import roman_to_int
from util.logger import Logger
import json
import logging
import os
import shutil
import threading
import time


# Global dictionary to store the number of threads processing each result.
thread_counts = {}
counter_lock = threading.Lock()


def parse_ability(url: str, max_generation: int, timeout: int, stop_event: threading.Event, logger: Logger) -> dict:
    """
    Parse the data of an ability from the PokeAPI.

    :param url: The URL of the result.
    :param max_generation: The maximum generation to parse.
    :param timeout: The timeout for the request.
    :param stop_event: The event to signal when the worker should stop.
    :param logger: The logger to log messages.
    :return: A dictionary with the result data.
    """

    # Fetch the data from the API.
    data = request_data(url, timeout, stop_event, logger)
    if data is None:
        return data

    # Check generation
    generation = roman_to_int(data["generation"]["name"].split("-")[1])
    if generation > max_generation:
        return None

    ability = {}

    # General ability information.
    ability["name"] = data["name"]
    ability["generation"] = data["generation"]["name"]
    ability["pokemon"] = {
        pokemon["pokemon"]["name"]: {
            "is_hidden": pokemon["is_hidden"],
            "slot": pokemon["slot"],
        }
        for pokemon in data["pokemon"]
    }

    # Ability effect and flavor text entries.
    effect_entry = next((entry for entry in data["effect_entries"] if entry["language"]["name"] == "en"), None)
    ability["effect"] = "" if effect_entry is None else effect_entry["effect"]
    ability["short_effect"] = "" if effect_entry is None else effect_entry["short_effect"]
    ability["effect_changes"] = {
        change["version_group"]["name"]: next(
            (entry for entry in change["effect_entries"] if entry["language"]["name"] == "en"), ""
        )["effect"]
        for change in data["effect_changes"]
    }
    ability["flavor_text_entries"] = {
        entry["version_group"]["name"]: entry["flavor_text"]
        for entry in data["flavor_text_entries"]
        if entry["language"]["name"] == "en"
    }

    return ability


def worker(q: Queue, thread_id: int, max_generation: int, timeout: int, stop_event: threading.Event, logger: Logger):
    """
    Worker function that continually processes results from the queue.

    :param q: The queue to retrieve results from.
    :param thread_id: The ID of the thread.
    :param max_generation: The maximum generation to parse.
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
        data = parse_ability(url, max_generation, timeout, stop_event, logger)
        if data is None:
            logger.log(logging.ERROR, f'Failed to parse result "{name}" from "{url}".')
            break
        else:
            logger.log(logging.INFO, f'Succesfully parsed result "{name}" from "{url}".')
            json_dump = json.dumps(data, indent=4)
            save(f"data/abilities/{name}.json", json_dump, logger)
            save(f"data-bk/abilities/{name}.json", json_dump, logger)
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
    MAX_GENERATION = int(os.getenv("MAX_GENERATION"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    LOG = os.getenv("LOG") == "True"
    logger = Logger("Ability Parser", "logs/ability_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Delete the existing data directory
    logger.log(logging.INFO, "Deleting existing data directory.")
    if os.path.exists("data/abilities"):
        shutil.rmtree("data/abilities")
    logger.log(logging.INFO, "Creating new data directory.")
    os.makedirs("data/abilities")

    # Build the API URL and fetch results.
    stop_event = threading.Event()
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/ability/?offset={offset}&limit={limit}"
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
        t = threading.Thread(target=worker, args=(q, i + 1, MAX_GENERATION, TIMEOUT, stop_event, logger))
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
