from dotenv import load_dotenv
from util.data import request_data
from util.file import save
from util.logger import Logger
import logging
import json
import os
import threading


def parse_item(url: str, timeout: int) -> dict:
    """
    Parse the data of an item from the PokeAPI.

    :param url: The url of the item.
    :param timeout: The timeout of the request.
    :return: The data of the item.
    """
    data = request_data(url, timeout)
    if data is None:
        return data
    item = {}

    # Item data
    item["name"] = data["name"]
    item["cost"] = data["cost"]
    item["category"] = data["category"]["name"]
    item["sprite"] = data["sprites"]["default"]
    item["games"] = [game["generation"]["name"] for game in data["game_indices"]]
    item["held_by"] = {
        pokemon.get("name", "?"): {
            version["version"]["name"]: version["rarity"] for version in pokemon["version_details"]
        }
        for pokemon in data["held_by_pokemon"]
    }

    # Item effects
    effect_entry = next((entry for entry in data["effect_entries"] if entry["language"]["name"] == "en"), None)
    item["effect"] = "" if effect_entry is None else effect_entry["effect"]
    item["short_effect"] = "" if effect_entry is None else effect_entry["short_effect"]
    item["flavor_text_entries"] = {
        entry["version_group"]["name"]: entry["text"]
        for entry in data["flavor_text_entries"]
        if entry["language"]["name"] == "en"
    }

    # Item attributes
    item["fling_power"] = data["fling_power"]
    fling_effect = data["fling_effect"]
    if fling_effect is not None:
        fling_effect = request_data(fling_effect["url"], timeout)
        if fling_effect is not None:
            effect_entries = fling_effect["effect_entries"]
            fling_effect = next((entry for entry in effect_entries if entry["language"]["name"] == "en"), None)
    item["fling_effect"] = "" if fling_effect is None else fling_effect["effect"]
    item["attributes"] = [attribute["name"] for attribute in data["attributes"]]

    return item


def parse_item_range(items: list, timeout: int, logger: Logger) -> None:
    for item in items:
        name = item["name"]
        data = parse_item(item["url"], timeout)
        if data is None:
            logger.log(logging.ERROR, f"Failed to parse item {name}")
            break

        logger.log(logging.INFO, f"Parsed item {name}")
        save(f"data/items/{name}.json", json.dumps(data, indent=4), logger)


def main():
    """
    Parse the data of items from the PokeAPI.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))

    logger = Logger("main", "logs/item_parser.log", LOG)

    # Load all item names
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    items = request_data(f"https://pokeapi.co/api/v2/item/?offset={offset}&limit={limit}", TIMEOUT)["results"]

    # Calculate the range each thread will handle
    total_items = len(items)
    chunk_size = total_items // THREADS
    remainder = total_items % THREADS

    threads = []
    start_index = STARTING_INDEX

    for t in range(THREADS):
        # Calculate the end index for each thread's range
        end_index = start_index + chunk_size - 1
        if remainder > 0:
            end_index += 1
            remainder -= 1

        # Start each thread to handle a specific range of items
        thread = threading.Thread(target=parse_item_range, args=(items[start_index:end_index], TIMEOUT, logger))
        threads.append(thread)
        thread.start()

        # Update the start_index for the next thread
        start_index = end_index + 1

    # Ensure all threads are completed
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
