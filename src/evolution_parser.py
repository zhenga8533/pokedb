from dotenv import load_dotenv
from queue import Queue, Empty
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import json
import glob
import logging
import os
import signal
import sys
import threading
import time


def parse_evolution(num: int, logger: Logger, timeout: int) -> dict:
    """
    Parse the data of an evolution chain from the PokeAPI.

    :param num: The number of the evolution chain.
    :param logger: The logger to log messages.
    :param timeout: The timeout of the request.
    :return: The data of the evolution chain.
    """

    url = f"https://pokeapi.co/api/v2/evolution-chain/{num}"
    data = request_data(url, timeout)
    if data is None:
        return data

    pokemon = []

    def parse_evolution_line(chain: dict) -> dict:
        """
        Recursively parse an evolution chain.
        """

        name = chain["species"]["name"]
        pokemon.append(name)
        evolutions = []
        for evolution in chain["evolves_to"]:
            evolutions.append(parse_evolution_line(evolution))
        return {
            "name": name,
            "evolution_details": chain["evolution_details"],
            "evolutions": evolutions,
        }

    evolutions = [parse_evolution_line(data["chain"])]

    # For every species found in the chain, update all matching Pokémon files.
    for species in pokemon:
        file_pattern = f"data/pokemon/{species}*.json"
        files = glob.glob(file_pattern)
        for file_path in files:
            pokemon_data = json.loads(load(file_path, logger))
            pokemon_data["evolutions"] = evolutions
            save(file_path, json.dumps(pokemon_data, indent=4), logger)

    return data


def worker(q: Queue, logger: Logger, timeout: int, stop_event: threading.Event) -> None:
    """
    Worker thread function: repeatedly retrieves an evolution chain number from the queue,
    parses the evolution chain, and logs the result.

    :param q: The queue of evolution chain numbers.
    :param logger: The logger to log messages.
    :param timeout: The timeout of the request.
    :param stop_event: The event to signal the worker to stop.
    :return: None
    """

    while not stop_event.is_set():
        try:
            # Use a timeout so the worker wakes up periodically.
            chain_number = q.get(timeout=1)
        except Empty:
            continue

        # Check one more time after retrieving the task.
        if stop_event.is_set():
            q.task_done()
            break

        logger.log(logging.INFO, f"Searching for Evolution #{chain_number}...")
        try:
            result = parse_evolution(chain_number, logger, timeout)
        except KeyboardInterrupt:
            # Allow Ctrl+C to interrupt the worker immediately.
            q.task_done()
            raise

        if result is None:
            logger.log(logging.ERROR, f"Evolution #{chain_number} was not found.")
        else:
            logger.log(logging.INFO, f"Evolution #{chain_number} was parsed successfully.")
        q.task_done()


def main():
    """
    Main function to load configuration, populate the task queue with evolution chain numbers,
    and start worker threads.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/evolution_parser.log", LOG)

    # Create a queue and populate it with evolution chain numbers.
    q = Queue()
    for num in range(STARTING_INDEX, ENDING_INDEX + 1):
        q.put(num)

    # Create an event to signal workers to stop.
    stop_event = threading.Event()

    # Start a fixed pool of worker threads.
    threads = []
    for _ in range(THREADS):
        t = threading.Thread(target=worker, args=(q, logger, TIMEOUT, stop_event))
        t.daemon = True
        t.start()
        threads.append(t)

    # Install a signal handler for SIGINT (Ctrl+C).
    def signal_handler(sig, frame):
        logger.log(logging.INFO, "Received SIGINT, shutting down...")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Instead of blocking on q.join(), use a polling loop so Ctrl+C is handled promptly.
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.log(logging.INFO, "KeyboardInterrupt caught in main loop, shutting down...")
        stop_event.set()
        time.sleep(1)

    # Ensure all threads have finished execution.
    for t in threads:
        t.join()

    logger.log(logging.INFO, "Shutdown complete.")


if __name__ == "__main__":
    main()
