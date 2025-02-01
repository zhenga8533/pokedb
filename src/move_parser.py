from dotenv import load_dotenv
from queue import Queue, Empty
from util.data import request_data
from util.file import save
from util.logger import Logger
import json
import logging
import os
import signal
import sys
import threading
import time


def parse_move(num: int, timeout: int) -> dict:
    """
    Parse the data of a move from the PokeAPI.

    :param num: The number of the move.
    :param timeout: The timeout for the request.
    :return: A dictionary with the move data.
    """

    url = f"https://pokeapi.co/api/v2/move/{num}"
    data = request_data(url, timeout)
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
        machine_data = request_data(machine, timeout)
        machine_name = machine_data["item"]["name"]
        machine_version = machine_data["version_group"]["name"]
        move["machines"][machine_version] = machine_name

    return move


def worker(q: Queue, timeout: int, logger: Logger, stop_event: threading.Event) -> None:
    """
    Worker thread function: repeatedly pulls a move number from the queue,
    parses the move data, and saves it.

    :param q: A thread-safe queue containing move numbers.
    :param timeout: The timeout for API requests.
    :param logger: Logger instance for logging messages.
    :param stop_event: Event to signal when to stop processing.
    """

    while not stop_event.is_set():
        try:
            # Use a timeout so the thread periodically wakes up to check stop_event.
            move_num = q.get(timeout=1)
        except Empty:
            continue

        # Check again in case a shutdown was requested.
        if stop_event.is_set():
            q.task_done()
            break

        logger.log(logging.INFO, f"Searching for Move #{move_num}...")
        try:
            move = parse_move(move_num, timeout)
        except KeyboardInterrupt:
            # Allow Ctrl+C to interrupt immediately.
            q.task_done()
            raise

        if move is None:
            logger.log(logging.ERROR, f"Move #{move_num} was not found.")
        else:
            logger.log(logging.INFO, f"{move['name']} was parsed successfully.")
            save(f"data/moves/{move['name']}.json", json.dumps(move, indent=4), logger)
            logger.log(logging.INFO, f"{move['name']} was saved successfully.")
        q.task_done()


def main():
    """
    Parse the data of moves from the PokeAPI using a pool of worker threads.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/move_parser.log", LOG)

    # Populate the queue with move numbers.
    q = Queue()
    for num in range(STARTING_INDEX, ENDING_INDEX + 1):
        q.put(num)

    # Create an event to signal worker threads to stop.
    stop_event = threading.Event()

    # Start a fixed number of worker threads.
    threads = []
    for _ in range(THREADS):
        t = threading.Thread(target=worker, args=(q, TIMEOUT, logger, stop_event))
        t.daemon = True
        t.start()
        threads.append(t)

    # Install a signal handler for SIGINT (Ctrl+C).
    def signal_handler(sig, frame):
        logger.log(logging.INFO, "Received SIGINT, shutting down...")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Instead of blocking on q.join(), use a polling loop to allow quick shutdown.
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.log(logging.INFO, "KeyboardInterrupt caught in main loop, shutting down...")
        stop_event.set()
        time.sleep(1)

    # Ensure all threads have finished.
    for t in threads:
        t.join()

    logger.log(logging.INFO, "Shutdown complete.")


if __name__ == "__main__":
    main()
