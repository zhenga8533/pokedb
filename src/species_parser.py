from dotenv import load_dotenv
from util.data import request_data
from util.file import load, save
from util.logger import Logger
import logging
import json
import os


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
    flavor_text_entries = [
        entry["flavor_text"] for entry in data["flavor_text_entries"] if entry["language"]["name"] == "en"
    ]
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
        pokemon["forms"] = forms
        save(file_path, json.dumps(pokemon, indent=4), logger)

    return data


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

    logger = Logger("main", "logs/species_parser.log", LOG)
    for i in range(STARTING_INDEX, ENDING_INDEX + 1):
        logger.log(logging.INFO, f"Searching for Species #{i}...")
        species = parse_species(i, logger, TIMEOUT)
        if species is None:
            logger.log(logging.ERROR, f"Species #{i} was not found.")
            break
        logger.log(logging.INFO, f"Species '{species["name"]}' was parsed successfully.")


if __name__ == "__main__":
    main()
