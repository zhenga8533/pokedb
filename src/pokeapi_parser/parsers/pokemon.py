import json
import os
from typing import Any, Dict, List, Optional, Union

import requests

from ..utils import get_english_entry
from .base import BaseParser


class PokemonParser(BaseParser):
    """
    A comprehensive parser for Pokémon species and all their forms/varieties.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        session: requests.Session,
        generation_version_groups: Dict[int, List[str]],
        target_gen: int,
        generation_dex_map: Dict[int, str],
    ):
        super().__init__(config, session, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Pokemon"
        self.output_dir_key_pokemon = "output_dir_pokemon"
        self.output_dir_key_form = "output_dir_form"
        self.evolution_cache: Dict[str, Any] = {}

    def _get_evolution_chain(self, chain_url: str) -> Optional[Dict[str, Any]]:
        """
        Recursively fetches and processes an evolution chain.

        Args:
            chain_url (str): The URL of the evolution chain to fetch.

        Returns:
            A nested dictionary representing the evolution chain, or None on failure.
        """
        if chain_url in self.evolution_cache:
            return self.evolution_cache[chain_url]
        try:
            response = self.session.get(chain_url, timeout=self.config["timeout"])
            response.raise_for_status()
            chain_data = response.json()["chain"]

            def recurse_chain(chain: Dict[str, Any]) -> Dict[str, Any]:
                species_name = chain["species"]["name"]
                evolves_to: List[Dict[str, Any]] = []
                for evolution in chain.get("evolves_to", []):
                    details_list = evolution.get("evolution_details", [])
                    details = details_list[0] if details_list else {}
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

    def _get_generation_data(
        self, data: Dict[str, Any], key: str, name_key: str, details_key: str, version_key: str
    ) -> Union[Dict[str, Any], Dict[str, int]]:
        """
        A generic helper to filter data (like moves or held items) by the target generation.

        Args:
            data (Dict[str, Any]): The raw Pokémon data dictionary.
            key (str): The top-level key for the data list (e.g., 'moves').
            name_key (str): The key for the item's name (e.g., 'move').
            details_key (str): The key for the version details list.
            version_key (str): The key for the version/version_group object.

        Returns:
            A dictionary of generation-specific data.
        """
        gen_data: Dict[str, Any] = {}
        if not self.generation_version_groups or self.target_gen is None:
            return {}

        target_groups = self.generation_version_groups.get(self.target_gen, [])
        for item in data.get(key, []):
            item_name = item[name_key]["name"]
            for details in item[details_key]:
                if details[version_key]["name"] in target_groups:
                    if name_key == "move":
                        method = details["move_learn_method"]["name"]
                        if method not in gen_data:
                            gen_data[method] = []
                        gen_data[method].append({"name": item_name, "level_learned_at": details["level_learned_at"]})
                    else:  # held_items
                        gen_data[item_name] = details["rarity"]
                        break
        return gen_data

    def _process_sprites(self, sprites: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filters the versions sprites object to only include the target generation.

        Args:
            sprites (Dict[str, Any]): The raw sprites object from the API.

        Returns:
            Dict[str, Any]: The sprites object with the 'versions' key filtered.
        """
        if not sprites or "versions" not in sprites or self.target_gen is None:
            return sprites
        roman_map = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii", 9: "ix"}
        gen_roman = roman_map.get(self.target_gen)
        if not gen_roman:
            sprites["versions"] = {}
            return sprites
        gen_key = f"generation-{gen_roman}"
        sprites["versions"] = {gen_key: sprites["versions"].get(gen_key, {})}
        return sprites

    def _get_generation_pokedex_numbers(self, pokedex_numbers: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Filters Pokédex numbers for national and the target generation's regional dex.

        Args:
            pokedex_numbers (List[Dict[str, Any]]): The list of Pokédex number entries.

        Returns:
            Dict[str, int]: A dictionary of relevant Pokédex numbers.
        """
        gen_numbers: Dict[str, int] = {}
        if not self.generation_dex_map or self.target_gen is None:
            return {}
        regional_dex_name = self.generation_dex_map.get(self.target_gen)
        for entry in pokedex_numbers:
            pokedex_name = entry["pokedex"]["name"]
            if pokedex_name == "national" or pokedex_name == regional_dex_name:
                gen_numbers[pokedex_name] = entry["entry_number"]
        return gen_numbers

    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, List[Dict[str, Any]]], str]]:
        """
        Processes a Pokémon species and all its varieties, saving them to pokemon/ and form/ dirs.

        Args:
            item_ref (Dict[str, str]): A dictionary containing the name and URL of the species.

        Returns:
            A dictionary containing lists of summary data for 'pokemon' and 'form', or an error string.
        """
        try:
            species_res = self.session.get(item_ref["url"], timeout=self.config["timeout"])
            species_res.raise_for_status()
            species_data = species_res.json()

            generation_url = species_data.get("generation", {}).get("url", "")
            if generation_url and self.target_gen and int(generation_url.split("/")[-2]) > self.target_gen:
                return None

            evolution_chain = self._get_evolution_chain(species_data["evolution_chain"]["url"])

            # This list will hold the summary dicts for ALL forms of this species
            summaries: Dict[str, List[Dict[str, Any]]] = {"pokemon": [], "form": []}

            for variety in species_data.get("varieties", []):
                pokemon_res = self.session.get(variety["pokemon"]["url"], timeout=self.config["timeout"])
                pokemon_res.raise_for_status()
                pokemon_data = pokemon_res.json()

                is_default_form = variety.get("is_default", False)

                # --- Create the combined JSON object ---
                cleaned_data: Dict[str, Any] = {
                    "id": pokemon_data["id"],
                    "name": pokemon_data["name"],
                    "species": species_data["name"],
                    "is_default": is_default_form,
                    "source_url": variety["pokemon"]["url"],
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
                    "height": pokemon_data["height"],
                    "weight": pokemon_data["weight"],
                    "cries": pokemon_data.get("cries", {}),
                    "sprites": self._process_sprites(pokemon_data.get("sprites", {})),
                }

                # --- Add species-level data ONLY to the default form ---
                if is_default_form:
                    cleaned_data.update(
                        {
                            "base_experience": pokemon_data["base_experience"],
                            "base_happiness": species_data.get("base_happiness"),
                            "capture_rate": species_data.get("capture_rate"),
                            "hatch_counter": species_data.get("hatch_counter"),
                            "gender_rate": species_data.get("gender_rate"),
                            "has_gender_differences": species_data.get("has_gender_differences"),
                            "is_baby": species_data.get("is_baby"),
                            "is_legendary": species_data.get("is_legendary"),
                            "is_mythical": species_data.get("is_mythical"),
                            "pokedex_numbers": self._get_generation_pokedex_numbers(
                                species_data.get("pokedex_numbers", [])
                            ),
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
                            "held_items": self._get_generation_data(
                                pokemon_data, "held_items", "item", "version_details", "version"
                            ),
                            "moves": self._get_generation_data(
                                pokemon_data, "moves", "move", "version_group_details", "version_group"
                            ),
                            "forms": [v["pokemon"]["name"] for v in species_data.get("varieties", [])],
                        }
                    )

                # --- Save the file and create the summary ---
                output_dir_key = self.output_dir_key_pokemon if is_default_form else self.output_dir_key_form
                output_dir = self.config[output_dir_key]
                os.makedirs(output_dir, exist_ok=True)
                file_path = os.path.join(output_dir, f"{cleaned_data['name']}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

                summary_key = "pokemon" if is_default_form else "form"
                summaries[summary_key].append(
                    {
                        "name": cleaned_data["name"],
                        "id": cleaned_data["id"],
                        "types": cleaned_data["types"],
                        "sprite": cleaned_data["sprites"].get("front_default"),
                    }
                )

            return summaries

        except requests.exceptions.RequestException as e:
            return f"Request failed for {item_ref['name']}: {e}"
        except (ValueError, KeyError, TypeError) as e:
            return f"Parsing failed for {item_ref['name']}: {e}"

    def run(self, all_items: List[Dict[str, str]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Override the base run method to handle the dict of summaries from process.

        Args:
            all_items (List[Dict[str, str]]): A list of all species references to process.

        Returns:
            A dictionary containing two keys, 'pokemon' and 'form', each with a list of summaries.
        """
        print(f"--- Running {self.item_name} Parser ---")
        if not all_items:
            print(f"No {self.item_name.lower()}s to process.")
            return {}

        print(f"Found {len(all_items)} species. Parsing all Pokemon and Forms...")
        errors: List[str] = []
        # We now have two distinct summary lists to build
        pokemon_summaries: List[Dict[str, Any]] = []
        form_summaries: List[Dict[str, Any]] = []

        from concurrent.futures import ThreadPoolExecutor, as_completed

        from tqdm import tqdm

        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_map = {executor.submit(self.process, item): item for item in all_items}
            for future in tqdm(as_completed(future_map), total=len(all_items), desc="Processing Species"):
                result = future.result()
                if isinstance(result, dict):
                    pokemon_summaries.extend(result.get("pokemon", []))
                    form_summaries.extend(result.get("form", []))
                elif result is not None:
                    errors.append(str(result))

        print("\nPokemon and Form processing complete.")
        if errors:
            print("\nThe following errors occurred:")
            for error in errors:
                print(f"- {error}")

        pokemon_summaries.sort(key=lambda x: x["id"])
        form_summaries.sort(key=lambda x: x["id"])

        return {"pokemon": pokemon_summaries, "form": form_summaries}
