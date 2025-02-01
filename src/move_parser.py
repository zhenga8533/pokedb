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


def parse_move(url: str, timeout: int, stop_event: threading.Event, logger: Logger) -> dict:
    """
    Parse the data of a result from the PokeAPI.

    :param url: The URL of the result.
    :param timeout: The timeout for the request.
    :param stop_event: The event to signal when the worker should stop.
    :param logger: The logger to log messages.
    :return: A dictionary with the result data.
    """

    data = request_data(url, timeout, stop_event, logger)
    if data is None:
        return data

    move = {}

    # Move data
    move["name"] = data["name"]
    move["accuracy"] = data["accuracy"]
    move["damage_class"] = data["damage_class"]["name"]
    move["power"] = data["power"]
    move["pp"] = data["pp"]
    move["priority"] = data["priority"]
    move["target"] = data["target"]["name"]
    move["type"] = data["type"]["name"]

    # Move effects
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

    # Move learn data
    move["generation"] = data["generation"]["name"]
    move["learned_by"] = [pokemon["name"] for pokemon in data["learned_by_pokemon"]]

    # Move machine data
    move["machines"] = {}
    machines = [machine["machine"]["url"] for machine in data["machines"]]
    for machine in machines:
        machine_data = request_data(machine, timeout, stop_event, logger)
        if machine_data:
            machine_name = machine_data["item"]["name"]
            machine_version = machine_data["version_group"]["name"]
            move["machines"][machine_version] = machine_name

    return move


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
        data = parse_move(url, timeout, stop_event, logger)
        if data is None:
            logger.log(logging.ERROR, f'Failed to parse result "{name}" from "{url}".')
        else:
            logger.log(logging.INFO, f'Succesfully parsed result "{name}" from "{url}".')
            save(f"data/moves/{name}.json", json.dumps(data, indent=4), logger)

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
    logger = Logger("Move Parser", "logs/move_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Build the API URL and fetch results.
    stop_event = threading.Event()
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/move/?offset={offset}&limit={limit}"
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
        logger.log(logging.INFO, "\nWork Summary:")
        for i in range(THREADS):
            tid = i + 1
            count = thread_counts.get(tid, 0)
            logger.log(logging.INFO, f"Thread {tid} processed {count} results.")


if __name__ == "__main__":
    main()
