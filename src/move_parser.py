from dotenv import load_dotenv
from util.data import request_data
from util.file import save
from util.logger import Logger
import logging
import json
import os


def parse_move(num: int, timeout: int) -> dict:
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
    if len(effect_entries) == 0:
        move["effect"] = ""
    else:
        effect_entry = next(entry for entry in (effect_entries) if entry["language"]["name"] == "en")
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


def main():
    """
    Parse the data of moves from the PokeAPI.

    :return: None
    """

    load_dotenv()
    LOG = os.getenv("LOG") == "True"
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))

    logger = Logger("main", "logs/move_parser.log", LOG)
    for i in range(STARTING_INDEX, ENDING_INDEX + 1):
        logger.log(logging.INFO, f"Searching for Move #{i}...")
        move = parse_move(i, TIMEOUT)
        if move is None:
            logger.log(logging.ERROR, f"Move #{i} was not found.")
            break

        logger.log(logging.INFO, f"{move["name"]} was parsed successfully.")
        save(f"data/moves/{move["name"]}.json", json.dumps(move, indent=4), logger)
        logger.log(logging.INFO, f"{move["name"]} was saved successfully.")


if __name__ == "__main__":
    main()
