from dotenv import load_dotenv
from queue import Queue, Empty
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import json
import logging
import os
import signal
import sys
import threading
import time


def parse_species(num: int, logger: Logger, timeout: int) -> dict:
    """
    Parse the data of a species from the PokeAPI.

    :param num: The number of the species.
    :param logger: The logger to log messages.
    :param timeout: The timeout for the request.
    :return: The data of the species, or None if not found.
    """

    url = f"https://pokeapi.co/api/v2/pokemon-species/{num}"
    data = request_data(url, timeout)
    if data is None:
        return data

    base_happiness = data["base_happiness"]
    capture_rate = data["capture_rate"]
    color = data["color"]["name"]
    egg_groups = [group["name"] for group in data["egg_groups"]]
    shape = data["shape"]["name"]
    flavor_text_entries = {
        entry["version"]["name"]: entry["flavor_text"]
        for entry in data["flavor_text_entries"]
        if entry["language"]["name"] == "en"
    }
    form_descriptions = [
        description["description"]
        for description in data["form_descriptions"]
        if description["language"]["name"] == "en"
    ]
    form_switchable = data["forms_switchable"]
    female_rate = data["gender_rate"]
    genus = next(entry["genus"] for entry in data["genera"] if entry["language"]["name"] == "en")
    generation = data["generation"]["name"]
    growth_rate = data["growth_rate"]["name"]
    habitat = data["habitat"]["name"] if data["habitat"] is not None else None
    has_gender_differences = data["has_gender_differences"]
    hatch_counter = data["hatch_counter"]
    is_baby = data["is_baby"]
    is_legendary = data["is_legendary"]
    is_mythical = data["is_mythical"]
    pokedex_numbers = {entry["pokedex"]["name"]: entry["entry_number"] for entry in data["pokedex_numbers"]}
    species = data["name"]
    forms = [form["pokemon"]["name"] for form in data["varieties"]]

    # For every variety (i.e. every Pokémon belonging to this species),
    # load its file and update its species-related data.
    for pokemon_entry in data["varieties"]:
        name = pokemon_entry["pokemon"]["name"]
        file_path = f"data/pokemon/{name}.json"
        pokemon = json.loads(load(file_path, logger))
        pokemon["base_happiness"] = base_happiness
        pokemon["capture_rate"] = capture_rate
        pokemon["color"] = color
        pokemon["egg_groups"] = egg_groups
        pokemon["shape"] = shape
        pokemon["flavor_text_entries"] = flavor_text_entries
        pokemon["form_descriptions"] = form_descriptions
        pokemon["form_switchable"] = form_switchable
        pokemon["female_rate"] = female_rate
        pokemon["genus"] = genus
        pokemon["generation"] = generation
        pokemon["growth_rate"] = growth_rate
        pokemon["habitat"] = habitat
        pokemon["has_gender_differences"] = has_gender_differences
        pokemon["hatch_counter"] = hatch_counter
        pokemon["is_baby"] = is_baby
        pokemon["is_legendary"] = is_legendary
        pokemon["is_mythical"] = is_mythical
        pokemon["pokedex_numbers"] = pokedex_numbers
        pokemon["species"] = species

        # Append any missing forms.
        if "forms" not in pokemon:
            pokemon["forms"] = []
        for form in forms:
            if form not in pokemon["forms"]:
                pokemon["forms"].append(form)

        save(file_path, json.dumps(pokemon, indent=4), logger)

    return data


def worker(q: Queue, timeout: int, logger: Logger, stop_event: threading.Event) -> None:
    """
    Worker thread function: continuously retrieves a species number from the queue,
    parses its data, and logs the result.

    If parsing a species fails (i.e. returns None), the worker logs the error and
    stops processing further species numbers.

    :param q: A thread-safe queue containing species numbers.
    :param timeout: The timeout for each API request.
    :param logger: Logger instance for logging messages.
    :param stop_event: Event to signal when to stop processing.
    """

    while not stop_event.is_set():
        try:
            # Use a timeout so the worker wakes periodically to check for shutdown.
            species_num = q.get(timeout=1)
        except Empty:
            continue

        if stop_event.is_set():
            q.task_done()
            break

        logger.log(logging.INFO, f"Searching for Species #{species_num}...")
        try:
            species_data = parse_species(species_num, logger, timeout)
        except KeyboardInterrupt:
            q.task_done()
            raise

        if species_data is None:
            logger.log(logging.ERROR, f"Species #{species_num} was not found.")
            q.task_done()
            # Stop processing further if a species is not found.
            break
        else:
            logger.log(logging.INFO, f"Species '{species_data['name']}' was parsed successfully.")
        q.task_done()


def main():
    """
    Parse the data of species from the PokeAPI using a fixed pool of worker threads.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/species_parser.log", LOG)

    # Populate the queue with species numbers.
    q = Queue()
    for num in range(STARTING_INDEX, ENDING_INDEX + 1):
        q.put(num)

    # Create an event to signal workers to stop.
    stop_event = threading.Event()

    # Start a fixed number of worker threads.
    threads = []
    for _ in range(THREADS):
        thread = threading.Thread(target=worker, args=(q, TIMEOUT, logger, stop_event))
        thread.daemon = True
        thread.start()
        threads.append(thread)

    # Install a signal handler for SIGINT (Ctrl+C).
    def signal_handler(sig, frame):
        logger.log(logging.INFO, "Received SIGINT, shutting down...")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Instead of blocking indefinitely on q.join(), poll the worker threads so Ctrl+C is handled promptly.
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        logger.log(logging.INFO, "KeyboardInterrupt caught in main loop, shutting down...")
        stop_event.set()
        time.sleep(1)

    # Ensure all threads have completed.
    for thread in threads:
        thread.join()

    logger.log(logging.INFO, "Shutdown complete.")


if __name__ == "__main__":
    main()
