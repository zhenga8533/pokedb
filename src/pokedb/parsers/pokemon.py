import json
import os
from typing import Any, Dict, List, Optional, Union

from ..api_client import ApiClient
from ..scraper import scrape_pokemon_changes
from ..utils import get_english_entry, int_to_roman
from .generation import GenerationParser


class PokemonParser(GenerationParser):
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
        is_historical: bool = False,
    ):
        super().__init__(config, api_client, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Species"
        self.api_endpoint = "pokemon_species"
        self.output_dir_key_pokemon = "output_dir_pokemon"
        self.output_dir_key_form = "output_dir_form"
        self.is_historical = is_historical

    def _apply_historical_changes(self, cleaned_data: Dict[str, Any]):
        """Applies scraped historical changes to the cleaned data."""
        if not self.target_gen:
            return

        changes = scrape_pokemon_changes(cleaned_data["species"], self.target_gen)
        if not changes:
            return

        if "ability" in changes:
            for i, ability in enumerate(cleaned_data.get("abilities", [])):
                if not ability.get("is_hidden"):
                    cleaned_data["abilities"][i]["name"] = changes["ability"]
                    break
        if "stats" in changes:
            cleaned_data["stats"].update(changes["stats"])
        if "types" in changes:
            cleaned_data["types"] = changes["types"]
        if "base_experience" in changes:
            cleaned_data["base_experience"] = changes["base_experience"]
        if "base_happiness" in changes:
            cleaned_data["base_happiness"] = changes["base_happiness"]
        if "capture_rate" in changes:
            cleaned_data["capture_rate"] = changes["capture_rate"]

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
        if not self.generation_version_groups or self.target_gen is None:
            return {}

        target_groups = self.generation_version_groups.get(self.target_gen, [])

        if key == "moves":
            temp_moves: Dict[tuple[str, str, int], set[str]] = {}
            for move_item in data.get("moves", []):
                move_name = move_item["move"]["name"]
                for details in move_item["version_group_details"]:
                    version_group = details["version_group"]["name"]
                    if version_group in target_groups:
                        learn_method = details["move_learn_method"]["name"]
                        level = details["level_learned_at"]
                        key_tuple = (move_name, learn_method, level)

                        if key_tuple not in temp_moves:
                            temp_moves[key_tuple] = set()
                        temp_moves[key_tuple].add(version_group)

            processed_moves: Dict[str, List[Dict[str, Any]]] = {}
            for (move_name, learn_method, level), games in temp_moves.items():
                if learn_method not in processed_moves:
                    processed_moves[learn_method] = []
                processed_moves[learn_method].append(
                    {"name": move_name, "level_learned_at": level, "version_groups": sorted(list(games))}
                )
            return processed_moves

        gen_data: Dict[str, Any] = {}
        for item in data.get(key, []):
            item_name = item[name_key]["name"]
            for details in item[details_key]:
                if details[version_key]["name"] in target_groups:
                    gen_data[item_name] = details["rarity"]
                    break
        return gen_data

    def _process_sprites(self, sprites: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refines the sprites object to only include the target generation's version data.
        """
        if not sprites:
            return {}

        processed_sprites = {k: v for k, v in sprites.items() if k != "versions"}

        if "versions" in sprites and self.target_gen is not None:
            try:
                gen_roman = int_to_roman(self.target_gen)
                gen_key = f"generation-{gen_roman.lower()}"
                if gen_key in sprites["versions"]:
                    processed_sprites["versions"] = sprites["versions"][gen_key]
            except ValueError:
                pass

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

    def _should_skip_form(self, pokemon_data: Dict[str, Any]) -> bool:
        """Checks if a form should be skipped based on the target generation."""
        form_url = pokemon_data.get("forms", [{}])[0].get("url")
        if not form_url:
            return True
        form_data = self.api_client.get(form_url)
        version_group_url = form_data.get("version_group", {}).get("url")
        if not version_group_url:
            return True
        version_group_data = self.api_client.get(version_group_url)
        form_introduction_gen = int(version_group_data["generation"]["url"].split("/")[-2])
        return self.target_gen is not None and form_introduction_gen > self.target_gen

    def _build_base_pokemon_data(
        self, pokemon_data: Dict[str, Any], species_data: Dict[str, Any], variety: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Builds the common data dictionary for any Pokémon form or variety."""
        return {
            "id": pokemon_data["id"],
            "name": pokemon_data["name"],
            "species": species_data["name"],
            "is_default": variety.get("is_default", False),
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

    def _add_default_species_data(
        self,
        cleaned_data: Dict[str, Any],
        pokemon_data: Dict[str, Any],
        species_data: Dict[str, Any],
        evolution_chain: Optional[Dict[str, Any]],
    ):
        """Adds extra fields that only apply to the default species."""
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
                "held_items": self._get_generation_data(
                    pokemon_data, "held_items", "item", "version_details", "version"
                ),
                "moves": self._get_generation_data(
                    pokemon_data, "moves", "move", "version_group_details", "version_group"
                ),
                "forms": [v["pokemon"]["name"] for v in species_data.get("varieties", [])],
            }
        )

    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, List[Dict[str, Any]]], str]]:
        """Processes a Pokémon species and all its varieties."""
        try:
            species_data = self.api_client.get(item_ref["url"])
            evolution_chain = self._get_evolution_chain(species_data["evolution_chain"]["url"])
            summaries: Dict[str, List[Dict[str, Any]]] = {"pokemon": [], "form": []}

            for variety in species_data.get("varieties", []):
                pokemon_data = self.api_client.get(variety["pokemon"]["url"])
                is_default = variety.get("is_default", False)

                if not is_default and self._should_skip_form(pokemon_data):
                    continue

                cleaned_data = self._build_base_pokemon_data(pokemon_data, species_data, variety)

                if is_default:
                    self._add_default_species_data(cleaned_data, pokemon_data, species_data, evolution_chain)
                    if self.is_historical:
                        self._apply_historical_changes(cleaned_data)

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
