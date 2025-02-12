import json
import logging
import os

from dotenv import load_dotenv
from requests import Session

from util.file import save
from util.logger import Logger
from util.threading import ThreadingManager


def parse_species(url: str, pokemon: dict, session: Session, timeout: int, logger: Logger) -> dict:
    """
    Parse the species data of a Pokémon from the PokeAPI and update the provided dictionary.

    :param url: The URL of the species.
    :param pokemon: The dictionary to update with species data.
    :param session: The shared requests session.
    :param timeout: The timeout for the request.
    :param logger: The logger instance.
    :return: The updated Pokémon dictionary.
    """

    try:
        response = session.get(url, timeout=timeout)
    except Exception as e:
        logger.log(logging.ERROR, f"Request failed for species URL {url}: {e}", exc_info=True)
        return pokemon

    if response.status_code != 200:
        logger.log(logging.ERROR, f"Failed to request species URL {url}: {response.status_code}")
        return pokemon

    data = response.json()

    # Update the Pokémon dictionary with species data.
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
            "genus": next((entry["genus"] for entry in data["genera"] if entry["language"]["name"] == "en"), ""),
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


def parse_pokemon(url: str, session: Session, timeout: int, logger: Logger) -> dict:
    """
    Parse the data of a Pokémon from the PokeAPI using the shared session.

    :param url: The URL of the Pokémon.
    :param session: The shared requests session.
    :param timeout: The timeout for the request.
    :param logger: The logger instance.
    :return: A dictionary with the parsed Pokémon data.
    """

    try:
        response = session.get(url, timeout=timeout)
    except Exception as e:
        logger.log(logging.ERROR, f"Request failed for Pokémon URL {url}: {e}", exc_info=True)
        return None

    if response.status_code != 200:
        logger.log(logging.ERROR, f"Failed to request Pokémon URL {url}: {response.status_code}")
        return None

    data = response.json()

    pokemon = {}
    # Basic data.
    pokemon["name"] = data["name"]
    pokemon["id"] = data["id"]
    pokemon["height"] = data["height"] / 10
    pokemon["weight"] = data["weight"] / 10

    # Battle data.
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

    # Wild data.
    pokemon["base_experience"] = data["base_experience"]
    pokemon["held_items"] = {
        held_item["item"]["name"]: {
            rarity["version"]["name"]: rarity["rarity"] for rarity in held_item["version_details"]
        }
        for held_item in data["held_items"]
    }

    # Game data.
    pokemon["cry_latest"] = data.get("cries", {}).get("latest")
    pokemon["cry_legacy"] = data.get("cries", {}).get("legacy")
    pokemon["sprites"] = data["sprites"]

    # Forms and species data.
    pokemon["forms"] = [form["name"] for form in data["forms"][1:]]
    species_url = data["species"]["url"]
    parse_species(species_url, pokemon, session, timeout, logger)

    return pokemon


def process_pokemon_result(result: dict, session: Session, timeout: int, logger: Logger):
    """
    Process a Pokémon result by fetching its data from the API and saving it.

    :param result: A dictionary containing at least the 'name' and 'url' of the Pokémon.
    :param session: The shared requests session.
    :param timeout: The timeout for each API request.
    :param logger: The logger instance.
    """

    name = result["name"]
    url = result["url"]
    logger.log(logging.INFO, f'Processing Pokémon "{name}" from "{url}".')
    data = parse_pokemon(url, session, timeout, logger)
    if data is None:
        logger.log(logging.ERROR, f'Failed to parse Pokémon "{name}" from "{url}".')
    else:
        logger.log(logging.INFO, f'Successfully parsed Pokémon "{name}" from "{url}".')
        json_dump = json.dumps(data, indent=4)
        save(f"data/pokemon/{name}.json", json_dump, logger)
        save(f"data-bk/pokemon/{name}.json", json_dump, logger)


def main():
    """
    Main entry point for the Pokémon parser script.

    :return: None
    """

    # Load environment variables and setup logger.
    load_dotenv()
    STARTING_INDEX = int(os.getenv("STARTING_INDEX"))
    ENDING_INDEX = int(os.getenv("ENDING_INDEX"))
    TIMEOUT = int(os.getenv("TIMEOUT"))
    THREADS = int(os.getenv("THREADS"))
    LOG = os.getenv("LOG") == "True"

    logger = Logger("Pokemon Parser", "logs/pokemon_parser.log", LOG)
    logger.log(logging.INFO, "Successfully loaded environment variables.")

    # Build the API URL and fetch Pokémon index data.
    offset = STARTING_INDEX - 1
    limit = ENDING_INDEX - STARTING_INDEX + 1
    api_url = f"https://pokeapi.co/api/v2/pokemon/?offset={offset}&limit={limit}"

    # Create a ThreadingManager instance (which creates its own session with retry support).
    tm = ThreadingManager(threads=THREADS, timeout=TIMEOUT, logger=logger)

    try:
        logger.log(logging.INFO, f"Requesting Pokémon index data from '{api_url}'.")
        response = tm.session.get(api_url, timeout=TIMEOUT)
    except Exception as e:
        logger.log(logging.ERROR, f"Request to '{api_url}' failed: {e}", exc_info=True)
        return

    if response.status_code != 200:
        logger.log(logging.ERROR, f"Failed to fetch results from '{api_url}': {response.status_code}")
        return

    data = response.json()
    results = data.get("results")
    if not results:
        logger.log(logging.ERROR, "No results found in the API response.")
        return

    logger.log(logging.INFO, "Successfully fetched Pokémon index data from the API.")

    # Populate the shared queue with the results.
    tm.add_to_queue(results)
    # Run worker threads using the ThreadingManager.
    tm.run_workers(process_pokemon_result)


if __name__ == "__main__":
    main()
