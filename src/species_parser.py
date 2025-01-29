from dotenv import load_dotenv
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import logging
import json
import os
import threading


def parse_species(num: int, logger: Logger, timeout: int) -> dict:
    """
    Parse the data of a species from the PokeAPI.

    :param num: The number of the species.
    :param logger: The logger to log messages.
    :param timeout: The timeout of the request.
    :return: The data of the species.
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
    forms = [form["pokemon"]["name"] for form in data["varieties"]]

    for pokemon in data["varieties"]:
        name = pokemon["pokemon"]["name"]
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
        save(file_path, json.dumps(pokemon, indent=4), logger)

    return data


def parse_species_range(start_index: int, end_index: int, timeout: int, logger: Logger):
    """
    Parse species data for a range of species numbers.

    :param start_index: The starting species number.
    :param end_index: The ending species number.
    :param timeout: The timeout for requests.
    :param logger: Logger instance for logging.
    """

    for i in range(start_index, end_index + 1):
        logger.log(logging.INFO, f"Searching for Species #{i}...")
        species = parse_species(i, logger, timeout)
        if species is None:
            logger.log(logging.ERROR, f"Species #{i} was not found.")
            break
        logger.log(logging.INFO, f"Species '{species['name']}' was parsed successfully.")


def main():
    """
    Parse the data of species from the PokeAPI.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/species_parser.log", LOG)

    # Calculate the range each thread will handle
    total_species = ENDING_INDEX - STARTING_INDEX + 1
    chunk_size = total_species // THREADS
    remainder = total_species % THREADS

    threads = []
    start_index = STARTING_INDEX

    for t in range(THREADS):
        # Calculate the end index for each thread's range
        end_index = start_index + chunk_size - 1
        if remainder > 0:
            end_index += 1
            remainder -= 1

        # Start each thread to handle a specific range of species numbers
        thread = threading.Thread(target=parse_species_range, args=(start_index, end_index, TIMEOUT, logger))
        threads.append(thread)
        thread.start()

        # Update the start_index for the next thread
        start_index = end_index + 1

    # Ensure all threads are completed
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
