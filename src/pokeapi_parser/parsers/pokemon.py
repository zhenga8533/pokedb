import json
import os

import requests

from ..utils import get_english_entry
from .base import BaseParser


class PokemonParser(BaseParser):
    """A parser for Pokémon."""

    def __init__(self, config, session, generation_version_groups, target_gen, generation_dex_map):
        super().__init__(config, session, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Pokemon"
        self.api_endpoint = "pokemon"
        self.output_dir_key = "output_dir_pokemon"
        self.evolution_cache = {}

    def _get_evolution_chain(self, chain_url):
        """Recursively fetches and processes an evolution chain."""
        if chain_url in self.evolution_cache:
            return self.evolution_cache[chain_url]

        try:
            response = self.session.get(chain_url, timeout=self.config["timeout"])
            response.raise_for_status()
            chain_data = response.json()["chain"]

            def recurse_chain(chain):
                species_name = chain["species"]["name"]
                evolves_to = []
                for evolution in chain.get("evolves_to", []):
                    evolution_details_list = evolution.get("evolution_details", [])
                    details = evolution_details_list[0] if evolution_details_list else {}
                    next_evolution = recurse_chain(evolution)
                    evolves_to.append(
                        {
                            "species_name": next_evolution["species_name"],
                            "evolution_details": {
                                "item": (details.get("item") or {}).get("name"),
                                "trigger": (details.get("trigger") or {}).get("name"),
                                "gender": details.get("gender"),
                                "held_item": (details.get("held_item") or {}).get("name"),
                                "known_move": (details.get("known_move") or {}).get("name"),
                                "known_move_type": (details.get("known_move_type") or {}).get("name"),
                                "location": (details.get("location") or {}).get("name"),
                                "min_level": details.get("min_level"),
                                "min_happiness": details.get("min_happiness"),
                                "min_beauty": details.get("min_beauty"),
                                "min_affection": details.get("min_affection"),
                                "needs_overworld_rain": details.get("needs_overworld_rain"),
                                "party_species": (details.get("party_species") or {}).get("name"),
                                "party_type": (details.get("party_type") or {}).get("name"),
                                "relative_physical_stats": details.get("relative_physical_stats"),
                                "time_of_day": details.get("time_of_day"),
                                "trade_species": (details.get("trade_species") or {}).get("name"),
                                "turn_upside_down": details.get("turn_upside_down"),
                            },
                            "evolves_to": next_evolution["evolves_to"],
                        }
                    )
                return {"species_name": species_name, "evolves_to": evolves_to}

            result = recurse_chain(chain_data)
            self.evolution_cache[chain_url] = result
            return result

        except requests.exceptions.RequestException as e:
            print(f"Warning: Could not fetch evolution chain from {chain_url}. Error: {e}")
            return None

    def _get_generation_moves(self, moves):
        """Filters moves that are available in the target generation."""
        gen_moves = {}
        target_version_groups = self.generation_version_groups.get(self.target_gen, [])
        for move in moves:
            move_name = move["move"]["name"]
            for version_group_details in move["version_group_details"]:
                if version_group_details["version_group"]["name"] in target_version_groups:
                    learn_method = version_group_details["move_learn_method"]["name"]
                    if learn_method not in gen_moves:
                        gen_moves[learn_method] = []
                    gen_moves[learn_method].append(
                        {
                            "name": move_name,
                            "level_learned_at": version_group_details["level_learned_at"],
                        }
                    )
        return gen_moves

    def _process_sprites(self, sprites):
        """
        Filters the versions sprites object to only include the target generation.
        """
        if not sprites or "versions" not in sprites:
            return sprites

        # Map generation number to the API's roman numeral string
        roman_map = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii", 9: "ix"}
        gen_roman = roman_map.get(self.target_gen)
        if not gen_roman:
            sprites["versions"] = {}  # Clear versions if gen is not mapped
            return sprites

        gen_key = f"generation-{gen_roman}"

        # Keep only the target generation's sprites
        filtered_versions = {gen_key: sprites["versions"].get(gen_key, {})}
        sprites["versions"] = filtered_versions

        return sprites

    def _get_generation_held_items(self, held_items):
        """Filters held items for the target generation and simplifies the structure."""
        gen_items = {}
        # Get all version group names for the target generation
        target_version_group_names = self.generation_version_groups.get(self.target_gen, [])

        for item in held_items:
            item_name = item["item"]["name"]
            for version_details in item["version_details"]:
                # The version name in the held_item details matches a version name, not version_group
                # We need to find which version_group this version belongs to.
                # This is complex, so for now we'll assume a version name contains a keyword
                # from the version_group names for simplicity. A truly robust solution
                # would pre-fetch all version and version_group data.
                version_name = version_details["version"]["name"]
                if any(vg_name in version_name for vg_name in target_version_group_names):
                    gen_items[item_name] = version_details["rarity"]
                    break
        return gen_items

    def _get_generation_pokedex_numbers(self, pokedex_numbers):
        """Filters Pokédex numbers for national and the target generation's regional dex."""
        gen_numbers = {}
        regional_dex_name = self.generation_dex_map.get(self.target_gen)

        for entry in pokedex_numbers:
            pokedex_name = entry["pokedex"]["name"]
            if pokedex_name == "national" or pokedex_name == regional_dex_name:
                gen_numbers[pokedex_name] = entry["entry_number"]

        return gen_numbers

    def process(self, item_ref):
        """Processes a single Pokémon species from its API reference."""
        try:
            # --- Step 1: Fetch the SPECIES data ---
            species_response = self.session.get(item_ref["url"], timeout=self.config["timeout"])
            species_response.raise_for_status()
            species_data = species_response.json()

            # --- Step 2: Find the default variety and fetch the main POKEMON data ---
            default_pokemon_url = None
            for variety in species_data.get("varieties", []):
                if variety.get("is_default", False):
                    default_pokemon_url = variety["pokemon"]["url"]
                    break

            if not default_pokemon_url and species_data.get("varieties"):
                default_pokemon_url = species_data["varieties"][0]["pokemon"]["url"]

            if not default_pokemon_url:
                raise ValueError("No varieties found for this species")

            pokemon_response = self.session.get(default_pokemon_url, timeout=self.config["timeout"])
            pokemon_response.raise_for_status()
            pokemon_data = pokemon_response.json()

            # --- Step 3: Get Evolution Chain ---
            evolution_chain = self._get_evolution_chain(species_data["evolution_chain"]["url"])

            # --- Step 4: Combine data from all endpoints ---
            cleaned_data = {
                "id": pokemon_data["id"],
                "name": pokemon_data["name"],
                "species": species_data["name"],
                "source_url": item_ref["url"],
                "height": pokemon_data["height"],
                "weight": pokemon_data["weight"],
                "base_experience": pokemon_data["base_experience"],
                "base_happiness": species_data.get("base_happiness"),
                "capture_rate": species_data.get("capture_rate"),
                "hatch_counter": species_data.get("hatch_counter"),
                "gender_rate": species_data.get("gender_rate"),
                "has_gender_differences": species_data.get("has_gender_differences"),
                "is_baby": species_data.get("is_baby"),
                "is_legendary": species_data.get("is_legendary"),
                "is_mythical": species_data.get("is_mythical"),
                "cries": pokemon_data.get("cries", {}),
                "types": [t["type"]["name"] for t in pokemon_data.get("types", [])],
                "abilities": [
                    {"name": a["ability"]["name"], "is_hidden": a["is_hidden"], "slot": a["slot"]}
                    for a in pokemon_data.get("abilities", [])
                ],
                "stats": {s["stat"]["name"]: s["base_stat"] for s in pokemon_data.get("stats", [])},
                "ev_yield": [
                    {"stat": s["stat"]["name"], "effort": s["effort"]}
                    for s in pokemon_data.get("stats", [])
                    if s["effort"] > 0
                ],
                "held_items": self._get_generation_held_items(pokemon_data.get("held_items", [])),
                "forms": [form["name"] for form in pokemon_data.get("forms", [])],
                "sprites": self._process_sprites(pokemon_data.get("sprites", {})),
                "moves": self._get_generation_moves(pokemon_data.get("moves", [])),
                "pokedex_numbers": self._get_generation_pokedex_numbers(species_data.get("pokedex_numbers", [])),
                "color": species_data.get("color", {}).get("name"),
                "shape": species_data.get("shape", {}).get("name"),
                "egg_groups": [group["name"] for group in species_data.get("egg_groups", [])],
                "flavor_text": get_english_entry(
                    species_data.get("flavor_text_entries", []),
                    "flavor_text",
                    self.generation_version_groups,
                    self.target_gen,
                ),
                "genus": get_english_entry(species_data.get("genera", []), "genus"),
                "generation": species_data.get("generation", {}).get("name"),
                "evolution_chain": evolution_chain,
            }

            output_path = self.config[self.output_dir_key]
            os.makedirs(output_path, exist_ok=True)
            file_path = os.path.join(output_path, f"{cleaned_data['name']}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

            return {"name": cleaned_data["name"], "id": cleaned_data["id"], "types": cleaned_data["types"]}
        except requests.exceptions.RequestException as e:
            return f"Request failed for {item_ref['name']}: {e}"
        except (ValueError, KeyError, TypeError) as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
