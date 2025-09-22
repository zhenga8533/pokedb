import json
import os

import requests

from ..utils import get_english_entry
from .base import BaseParser


class PokemonParser(BaseParser):
    """A parser for Pokémon."""

    def __init__(self, config, session):
        super().__init__(config, session)
        self.item_name = "Pokemon"
        self.api_endpoint = "pokemon"
        self.output_dir_key = "output_dir_pokemon"

    def process(self, item_ref):
        """Processes a single Pokémon from its API reference."""
        try:
            response = self.session.get(item_ref["url"], timeout=self.config["timeout"])
            response.raise_for_status()
            pokemon_data = response.json()

            species_url = pokemon_data["species"]["url"]
            species_response = self.session.get(species_url, timeout=self.config["timeout"])
            species_response.raise_for_status()
            species_data = species_response.json()

            cleaned_data = {
                "id": pokemon_data["id"],
                "name": pokemon_data["name"],
                "height": pokemon_data["height"],
                "weight": pokemon_data["weight"],
                "base_experience": pokemon_data["base_experience"],
                "types": [t["type"]["name"] for t in pokemon_data.get("types", [])],
                "abilities": [
                    {"name": a["ability"]["name"], "is_hidden": a["is_hidden"], "slot": a["slot"]}
                    for a in pokemon_data.get("abilities", [])
                ],
                "stats": {s["stat"]["name"]: s["base_stat"] for s in pokemon_data.get("stats", [])},
                "sprites": {
                    "front_default": pokemon_data["sprites"]["front_default"],
                    "front_shiny": pokemon_data["sprites"]["front_shiny"],
                    "official_artwork": pokemon_data["sprites"]["other"]["official-artwork"]["front_default"],
                },
                "flavor_text": get_english_entry(species_data.get("flavor_text_entries", []), "flavor_text"),
                "genus": get_english_entry(species_data.get("genera", []), "genus"),
                "generation": species_data.get("generation", {}).get("name"),
                "capture_rate": species_data.get("capture_rate"),
                "growth_rate": species_data.get("growth_rate", {}).get("name"),
            }

            output_path = self.config[self.output_dir_key]
            os.makedirs(output_path, exist_ok=True)
            file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False)
            return None
        except requests.exceptions.RequestException as e:
            return f"Request failed for {item_ref['name']}: {e}"
        except (KeyError, TypeError) as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
