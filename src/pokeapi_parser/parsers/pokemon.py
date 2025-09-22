import json
import os
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..utils import get_english_entry
from .base import BaseParser


class PokemonParser(BaseParser):
    """
    A comprehensive parser for Pokémon species and all their forms/varieties.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        api_client: ApiClient,
        generation_version_groups: Dict[int, List[str]],
        target_gen: int,
        generation_dex_map: Dict[int, str],
    ):
        super().__init__(config, api_client, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Species"
        self.output_dir_key_pokemon = "output_dir_pokemon"
        self.output_dir_key_form = "output_dir_form"

    def _get_evolution_chain(self, chain_url: str) -> Optional[Dict[str, Any]]:
        """Recursively fetches and processes an evolution chain."""
        try:
            chain_data = self.api_client.get(chain_url)["chain"]

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

            return recurse_chain(chain_data)
        except Exception as e:
            print(f"Warning: Could not process evolution chain from {chain_url}. Error: {e}")
            return None

    def _get_generation_data(
        self, data: Dict[str, Any], key: str, name_key: str, details_key: str, version_key: str
    ) -> Dict[str, Any]:
        """A generic helper to filter data by the target generation."""
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
        Refines the sprites object by lifting the target generation's sprites
        to the top level and removing the 'versions' key.
        """
        if not sprites:
            return {}

        # Start with a copy of the sprites dictionary, excluding 'versions'
        processed_sprites = {k: v for k, v in sprites.items() if k != "versions"}

        # Find the target generation's sprites and merge them into the top level
        if "versions" in sprites and self.target_gen is not None:
            roman_map = {1: "i", 2: "ii", 3: "iii", 4: "iv", 5: "v", 6: "vi", 7: "vii", 8: "viii", 9: "ix"}
            gen_roman = roman_map.get(self.target_gen)
            if gen_roman:
                gen_key = f"generation-{gen_roman}"
                gen_sprites = sprites["versions"].get(gen_key, {})
                for game, game_sprites in gen_sprites.items():
                    for sprite_type, url in game_sprites.items():
                        if url:
                            # Create a descriptive key, e.g., 'scarlet-violet_front_shiny'
                            processed_sprites[f"{game}_{sprite_type}"] = url

        return {k: v for k, v in processed_sprites.items() if v is not None}

    def _get_generation_pokedex_numbers(self, pokedex_numbers: List[Dict[str, Any]]) -> Dict[str, int]:
        """Filters Pokédex numbers for national and the target generation's regional dex."""
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
        """Processes a Pokémon species and all its varieties."""
        try:
            species_data = self.api_client.get(item_ref["url"])
            generation_url = species_data.get("generation", {}).get("url", "")
            if generation_url and self.target_gen and int(generation_url.split("/")[-2]) > self.target_gen:
                return None

            evolution_chain = self._get_evolution_chain(species_data["evolution_chain"]["url"])
            summaries: Dict[str, List[Dict[str, Any]]] = {"pokemon": [], "form": []}

            for variety in species_data.get("varieties", []):
                pokemon_data = self.api_client.get(variety["pokemon"]["url"])
                is_default = variety.get("is_default", False)

                cleaned_data: Dict[str, Any] = {
                    "id": pokemon_data["id"],
                    "name": pokemon_data["name"],
                    "species": species_data["name"],
                    "is_default": is_default,
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

                if is_default:
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

                output_key = self.output_dir_key_pokemon if is_default else self.output_dir_key_form
                output_dir = self.config[output_key]
                os.makedirs(output_dir, exist_ok=True)
                file_path = os.path.join(output_dir, f"{cleaned_data['name']}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cleaned_data, f, indent=4, ensure_ascii=False)

                summary_key = "pokemon" if is_default else "form"
                summaries[summary_key].append(
                    {
                        "name": cleaned_data["name"],
                        "id": cleaned_data["id"],
                        "types": cleaned_data["types"],
                        "sprite": cleaned_data["sprites"].get("front_default"),
                    }
                )

            return summaries
        except Exception as e:
            return f"Parsing failed for {item_ref['name']}: {e}"
