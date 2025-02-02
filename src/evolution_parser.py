from dotenv import load_dotenv
from queue import Queue, Empty
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import glob
import json
import logging
import os
import threading
import time


# Global dictionary to store the number of threads processing each result.
thread_counts = {}
counter_lock = threading.Lock()


def parse_evolution_line(chain: dict, pokemon: list) -> dict:
    """
    Recursively parse an evolution chain.

    :param chain: The chain to parse.
    :param pokemon: The list of pokemon to update.
    :return: A dictionary with the parsed evolution data.
    """

    name = chain["species"]["name"]
    pokemon.append(name)
    evolutions = []
    for evolution in chain["evolves_to"]:
        evolutions.append(parse_evolution_line(evolution, pokemon))
    return {
        "name": name,
        "evolution_details": chain["evolution_details"],
        "evolutions": evolutions,
    }


def parse_evolution(url: str, timeout: int, stop_event: threading.Event, logger: Logger) -> dict:
    """
    Parse the data of an evolution line from the PokeAPI.

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

    # Set up the data structures to store the parsed evolution data.
    pokemon = []
    evolutions = [parse_evolution_line(data["chain"], pokemon)]

    # Update the pokemon data with the parsed evolution data.
    for species in pokemon:
        file_pattern = f"data/pokemon/{species}*.json"
        files = glob.glob(file_pattern)

        # Loop through all files of the pokemon species
        for file_path in files:
            pokemon_data = json.loads(load(file_path, logger))
            pokemon_data["evolutions"] = evolutions
            save(file_path, json.dumps(pokemon_data, indent=4), logger)

    return data


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
            url = result["url"]
        except Empty:
            # No more results in the queue: exit the loop.
            break

        # Process and save the result data.
        logger.log(logging.INFO, f'Thread {thread_id} processing "{url}".')
        data = parse_evolution(url, timeout, stop_event, logger)
        if data is None:
            logger.log(logging.ERROR, f'Failed to parse result "{url}".')
        else:
            logger.log(logging.INFO, f'Succesfully parsed result "{url}".')

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
    logger = Logger("Evolution Parser", "logs/evolution_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Build the API URL and fetch results.
    stop_event = threading.Event()
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/evolution-chain/?offset={offset}&limit={limit}"
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
