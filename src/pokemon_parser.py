from dotenv import load_dotenv
from util.data import request_data
from util.file import save
from util.logger import Logger
import logging
import json
import os


def parse_pokemon(num: int, timeout: int) -> dict:
    """
    Parse the data of a pokemon from the PokeAPI.

    :param num: The number of the pokemon.
    :param timeout: The timeout of the request.
    :return: The data of the pokemon.
    """

    url = f"https://pokeapi.co/api/v2/pokemon/{num}"
    data = request_data(url, timeout)
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
    pokemon["types"] = [type["type"]["name"] for type in data["types"]]

    # Wild data
    pokemon["base_experience"] = data["base_experience"]
    pokemon["held_items"] = [
        {
            "name": held_item["item"]["name"],
            "rarity": [
                {
                    "version": rarity["version"]["name"],
                    "rarity": rarity["rarity"],
                }
                for rarity in held_item["version_details"]
            ],
        }
        for held_item in data["held_items"]
    ]

    # Game data
    pokemon["cry_latest"] = data["cries"]["latest"]
    pokemon["cry_legacy"] = data["cries"]["legacy"]
    pokemon["sprites"] = data["sprites"]

    return pokemon


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

    logger = Logger("main", "logs/pokemon_parser.log", LOG)
    for i in range(STARTING_INDEX, ENDING_INDEX + 1):
        logger.log(logging.INFO, f"Searching for Pokemon #{i}...")
        pokemon = parse_pokemon(i, TIMEOUT)
        if pokemon is None:
            logger.log(logging.ERROR, f"Pokemon #{i} was not found.")
            break

        logger.log(logging.INFO, f"{pokemon["name"]} was parsed successfully.")
        save(f"data/pokemon/{pokemon["name"]}.json", json.dumps(pokemon, indent=4), logger)
        logger.log(logging.INFO, f"{pokemon["name"]} was saved successfully.")


if __name__ == "__main__":
    main()
