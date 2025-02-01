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


def parse_pokemon(num: int, timeout: int, logger: Logger) -> dict:
    """
    Parse the data of a Pokémon from the PokeAPI.

    :param num: The Pokémon number.
    :param timeout: The timeout for the request.
    :param logger: Logger instance for logging.
    :return: A dictionary with the Pokémon data, or None if not found.
    """

    url = f"https://pokeapi.co/api/v2/pokemon/{num}"
    data = request_data(url, timeout)
    if data is None:
        logger.log(logging.ERROR, f"Pokemon #{num} was not found.")
        return None

    pokemon = {}
    # Species data
    pokemon["name"] = data["name"]
    pokemon["id"] = data["id"]
    pokemon["height"] = data["height"] / 10
    pokemon["weight"] = data["weight"] / 10

    # Battle data
    pokemon["abilities"] = [
        {
            "name": ability["ability"]["name"],
            "is_hidden": ability["is_hidden"],
            "slot": ability["slot"],
        }
        for ability in data["abilities"]
    ]
    pokemon["moves"] = {
        version_name: [
            {
                "name": move["move"]["name"],
                "level_learned_at": version_group_detail["level_learned_at"],
                "learn_method": version_group_detail["move_learn_method"]["name"],
            }
            for move in data["moves"]
            for version_group_detail in move["version_group_details"]
            if version_group_detail["version_group"]["name"] == version_name
        ]
        for version_name in {
            version_group_detail["version_group"]["name"]
            for move in data["moves"]
            for version_group_detail in move["version_group_details"]
        }
    }
    pokemon["stats"] = {stat["stat"]["name"]: stat["base_stat"] for stat in data["stats"]}
    pokemon["ev_yield"] = {stat["stat"]["name"]: stat["effort"] for stat in data["stats"]}
    pokemon["types"] = [type_info["type"]["name"] for type_info in data["types"]]

    # Wild data
    pokemon["base_experience"] = data["base_experience"]
    pokemon["held_items"] = [
        {
            "name": held_item["item"]["name"],
            "rarity": {rarity["version"]["name"]: rarity["rarity"] for rarity in held_item["version_details"]},
        }
        for held_item in data["held_items"]
    ]

    # Game data
    pokemon["cry_latest"] = data["cries"]["latest"]
    pokemon["cry_legacy"] = data["cries"]["legacy"]
    pokemon["sprites"] = data["sprites"]

    # Get forms (skip the first element as in the original code)
    pokemon["forms"] = [form["name"] for form in data["forms"][1:]]

    return pokemon


def parse_and_save_pokemon(i: int, timeout: int, logger: Logger) -> bool:
    """
    Parses and saves the data for a given Pokémon number.

    :param i: The Pokémon number.
    :param timeout: The timeout for the request.
    :param logger: Logger instance for logging.
    :return: True if the Pokémon was parsed and saved successfully, otherwise False.
    """

    logger.log(logging.INFO, f"Searching for Pokemon #{i}...")
    pokemon = parse_pokemon(i, timeout, logger)
    if pokemon is None:
        return False

    logger.log(logging.INFO, f"{pokemon['name']} was parsed successfully.")
    save(f"data/pokemon/{pokemon['name']}.json", json.dumps(pokemon, indent=4), logger)
    logger.log(logging.INFO, f"{pokemon['name']} was saved successfully.")
    return True


def worker(q: Queue, timeout: int, logger: Logger, stop_event: threading.Event) -> None:
    """
    Worker thread function: continuously retrieves a Pokémon number from the queue,
    parses its data, and saves it. If a failure occurs, this worker stops processing.

    :param q: A thread-safe queue containing Pokémon numbers.
    :param timeout: The timeout for each request.
    :param logger: Logger instance for logging.
    :param stop_event: An event signaling when to stop processing.
    """

    while not stop_event.is_set():
        try:
            # Use a timeout so the worker wakes periodically to check stop_event.
            num = q.get(timeout=1)
        except Empty:
            continue

        if stop_event.is_set():
            q.task_done()
            break

        try:
            # If parsing/saving fails, this worker stops processing further numbers.
            if not parse_and_save_pokemon(num, timeout, logger):
                q.task_done()
                break
        except KeyboardInterrupt:
            q.task_done()
            raise

        q.task_done()


def main():
    """
    Parse the data of Pokémon from the PokeAPI using a fixed pool of worker threads.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/pokemon_parser.log", LOG)

    # Populate the queue with Pokémon numbers.
    q = Queue()
    for i in range(STARTING_INDEX, ENDING_INDEX + 1):
        q.put(i)

    # Create an event to signal workers to stop.
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

    # Instead of blocking indefinitely on q.join(), poll the threads so Ctrl+C is handled promptly.
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.log(logging.INFO, "KeyboardInterrupt caught in main loop, shutting down...")
        stop_event.set()
        time.sleep(1)

    # Ensure all threads have completed.
    for t in threads:
        t.join()

    logger.log(logging.INFO, "Shutdown complete.")


if __name__ == "__main__":
    main()
