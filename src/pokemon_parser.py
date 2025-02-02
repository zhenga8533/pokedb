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


def parse_species(url: str, pokemon: dict, timeout: int, stop_event: threading.Event, logger: Logger) -> dict:
    """
    Parse the species data of a result from the PokeAPI.

    :param url: The URL of the result.
    :param pokemon: The dictionary to update with the species data.
    :param timeout: The timeout for the request.
    :param stop_event: The event to signal when the worker should stop.
    :param logger: The logger to log messages.
    :return: A dictionary with the result data.
    """

    # Fetch the data from the API.
    data = request_data(url, timeout, stop_event, logger)
    if data is None:
        return data

    # Update the pokemon data with the parsed species data.
    pokemon.update(
        {
            "base_happiness": data["base_happiness"],
            "capture_rate": data["capture_rate"],
            "color": data["color"]["name"],
            "egg_groups": [group["name"] for group in data["egg_groups"]],
            "shape": data["shape"]["name"],
            "flavor_text_entries": {
                entry["version"]["name"]: entry["flavor_text"]
                for entry in data["flavor_text_entries"]
                if entry["language"]["name"] == "en"
            },
            "form_descriptions": [
                desc["description"] for desc in data["form_descriptions"] if desc["language"]["name"] == "en"
            ],
            "form_switchable": data["forms_switchable"],
            "female_rate": data["gender_rate"],
            "genus": next(entry["genus"] for entry in data["genera"] if entry["language"]["name"] == "en"),
            "generation": data["generation"]["name"],
            "growth_rate": data["growth_rate"]["name"],
            "habitat": data["habitat"]["name"] if data["habitat"] is not None else None,
            "has_gender_differences": data["has_gender_differences"],
            "hatch_counter": data["hatch_counter"],
            "is_baby": data["is_baby"],
            "is_legendary": data["is_legendary"],
            "is_mythical": data["is_mythical"],
            "pokedex_numbers": {entry["pokedex"]["name"]: entry["entry_number"] for entry in data["pokedex_numbers"]},
            "species": data["name"],
        }
    )

    # Append any missing forms.
    forms = [form["pokemon"]["name"] for form in data["varieties"]]
    pokemon.setdefault("forms", [])
    for form in forms:
        if form not in pokemon["forms"]:
            pokemon["forms"].append(form)

    return pokemon


def parse_pokemon(url: str, timeout: int, stop_event: threading.Event, logger: Logger) -> dict:
    """
    Parse the data of a result from the PokeAPI.

    :param url: The URL of the result.
    :param timeout: The timeout for the request.
    :param stop_event: The event to signal when the worker should stop.
    :param logger: The logger to log messages.
    :return: A dictionary with the result data.
    """

    # Fetch the data from the API.
    data = request_data(url, timeout, stop_event, logger)
    if data is None:
        return data

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

    # Get forms and species data
    pokemon["forms"] = [form["name"] for form in data["forms"][1:]]
    species_url = data["species"]["url"]
    parse_species(species_url, pokemon, timeout, stop_event, logger)

    return pokemon


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
        data = parse_pokemon(url, timeout, stop_event, logger)
        if data is None:
            logger.log(logging.ERROR, f'Failed to parse result "{name}" from "{url}".')
        else:
            logger.log(logging.INFO, f'Succesfully parsed result "{name}" from "{url}".')
            save(f"data/pokemon/{name}.json", json.dumps(data, indent=4), logger)

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
    logger = Logger("Pokemon Parser", "logs/pokemon_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Build the API URL and fetch results.
    stop_event = threading.Event()
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/pokemon/?offset={offset}&limit={limit}"
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
