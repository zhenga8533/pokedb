from dotenv import load_dotenv
from util.data import request_data
from util.file import save
from util.logger import Logger
import logging
import json
import os
import threading


def parse_pokemon(num: int, timeout: int, logger: Logger) -> dict:
    """
    Parse the data of a pokemon from the PokeAPI.

    :param num: The number of the pokemon.
    :param timeout: The timeout of the request.
    :param logger: Logger instance for logging.
    :return: The data of the pokemon.
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
    pokemon["types"] = [type["type"]["name"] for type in data["types"]]

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

    # Get forms
    pokemon["forms"] = [form["name"] for form in data["forms"][1:]]

    return pokemon


def parse_and_save_pokemon(i: int, timeout: int, logger: Logger):
    """
    Parses and saves the data for a given pokemon number.

    :param i: The pokemon number.
    :param timeout: The timeout of the request.
    :param logger: Logger instance for logging.
    """

    logger.log(logging.INFO, f"Searching for Pokemon #{i}...")
    pokemon = parse_pokemon(i, timeout, logger)
    if pokemon is None:
        return False

    logger.log(logging.INFO, f"{pokemon['name']} was parsed successfully.")
    save(f"data/pokemon/{pokemon['name']}.json", json.dumps(pokemon, indent=4), logger)
    logger.log(logging.INFO, f"{pokemon['name']} was saved successfully.")
    return True


def parse_pokemon_range(start_index: int, end_index: int, timeout: int, logger: Logger):
    """
    Parse and save pokemon data for a range of numbers.

    :param start_index: The starting pokemon number.
    :param end_index: The ending pokemon number.
    :param timeout: The timeout of the request.
    :param logger: Logger instance for logging.
    """
    for i in range(start_index, end_index + 1):
        if not parse_and_save_pokemon(i, timeout, logger):
            break


def main():
    """
    Parse the data of the pokemon from the PokeAPI.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/pokemon_parser.log", LOG)

    # Calculate the range each thread will handle
    total_pokemon = ENDING_INDEX - STARTING_INDEX + 1
    chunk_size = total_pokemon // THREADS
    remainder = total_pokemon % THREADS

    threads = []
    start_index = STARTING_INDEX

    for t in range(THREADS):
        # Calculate the end index for each thread's range
        end_index = start_index + chunk_size - 1
        if remainder > 0:
            end_index += 1
            remainder -= 1

        # Start each thread to handle a specific range of pokemon numbers
        thread = threading.Thread(target=parse_pokemon_range, args=(start_index, end_index, TIMEOUT, logger))
        threads.append(thread)
        thread.start()

        # Update the start_index for the next thread
        start_index = end_index + 1

    # Ensure all threads are completed
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
