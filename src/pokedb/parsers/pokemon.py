import copy
import json
import os
from typing import Any, Dict, List, Optional, Set, Union

from ..api_client import ApiClient
from ..scraper import scrape_pokemon_changes
from ..utils import get_all_english_entries_for_gen_by_game, get_english_entry, int_to_roman
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
        target_versions: Optional[Set[str]] = None,
    ):
        super().__init__(config, api_client, generation_version_groups, target_gen, generation_dex_map)
        self.item_name = "Species"
        self.api_endpoint = "pokemon_species"
        self.output_dir_key_pokemon = "output_dir_pokemon"
        self.output_dir_key_variant = "output_dir_variant"
        self.output_dir_key_transformation = "output_dir_transformation"
        self.output_dir_key_cosmetic = "output_dir_cosmetic"
        self.is_historical = is_historical
        self.target_versions = target_versions or set()

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
        if "ev_yield" in changes:
            cleaned_data["ev_yield"] = changes["ev_yield"]

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
                entity_name = details[version_key]["name"]

                is_relevant = False
                if key == "moves":
                    is_relevant = entity_name in target_groups
                elif key == "held_items":
                    is_relevant = entity_name in self.target_versions

                if is_relevant:
                    if key == "moves":
                        method = details["move_learn_method"]["name"]
                        level = details["level_learned_at"]
                        move_key = (item_name, level)
                        if method not in gen_data:
                            gen_data[method] = {}
                        if move_key not in gen_data[method]:
                            gen_data[method][move_key] = set()
                        gen_data[method][move_key].add(entity_name)
                    elif key == "held_items":
                        if item_name not in gen_data:
                            gen_data[item_name] = {}
                        gen_data[item_name][entity_name] = details["rarity"]

        if key == "moves":
            processed_moves: Dict[str, Any] = {}
            for method, move_groups in gen_data.items():
                processed_moves[method] = []
                for (move_name, level), games in move_groups.items():
                    processed_moves[method].append(
                        {"name": move_name, "level_learned_at": level, "version_groups": sorted(list(games))}
                    )
            return processed_moves

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

    def _should_skip_form(self, form_data: Dict[str, Any]) -> bool:
        """Checks if a form should be skipped based on the target generation."""
        version_group_url = form_data.get("version_group", {}).get("url")
        if not version_group_url:
            return False

        version_group_data = self.api_client.get(version_group_url)
        form_introduction_gen = int(version_group_data["generation"]["url"].split("/")[-2])
        return self.target_gen is not None and form_introduction_gen > self.target_gen

    def _build_base_pokemon_data(
        self, pokemon_data: Dict[str, Any], species_data: Dict[str, Any], source_url: str
    ) -> Dict[str, Any]:
        """Builds the common data dictionary for any Pokémon form or variety."""
        return {
            "id": pokemon_data["id"],
            "name": pokemon_data["name"],
            "species": species_data["name"],
            "is_default": pokemon_data.get("is_default", False),
            "source_url": source_url,
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
                "base_experience": pokemon_data.get("base_experience"),
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
                "flavor_text": get_all_english_entries_for_gen_by_game(
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
                "forms": [f["pokemon"]["name"] for f in species_data.get("varieties", [])],
            }
        )

    def process(self, item_ref: Dict[str, str]) -> Optional[Union[Dict[str, List[Dict[str, Any]]], str]]:
        """Processes a Pokémon species and all its varieties and forms."""
        species_name = ""
        try:
            species_data = self.api_client.get(item_ref["url"])
            species_name = species_data["name"]
            evolution_chain_url = species_data.get("evolution_chain", {}).get("url")
            evolution_chain = self._get_evolution_chain(evolution_chain_url) if evolution_chain_url else None

            summaries: Dict[str, List[Dict[str, Any]]] = {
                "pokemon": [],
                "variant": [],
                "transformation": [],
                "cosmetic": [],
            }

            varieties = species_data.get("varieties", [])

            if not varieties:
                default_pokemon_url = f"{self.config['api_base_url']}pokemon/{species_data['id']}"
                default_variety = {"is_default": True, "pokemon": {"name": species_name, "url": default_pokemon_url}}
                varieties = [default_variety]
            else:
                default_variety = next((v for v in varieties if v["is_default"]), varieties[0])

            default_pokemon_url = default_variety["pokemon"]["url"]
            default_pokemon_data = self.api_client.get(default_pokemon_url)

            default_template = self._build_base_pokemon_data(default_pokemon_data, species_data, default_pokemon_url)
            self._add_default_species_data(default_template, default_pokemon_data, species_data, evolution_chain)
            if self.is_historical:
                self._apply_historical_changes(default_template)

            output_dir = self.config[self.output_dir_key_pokemon]
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{default_template['name']}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(default_template, f, indent=4, ensure_ascii=False)
            summaries["pokemon"].append(
                {
                    "name": default_template["name"],
                    "id": default_template["id"],
                    "sprite": default_template["sprites"].get("front_default"),
                }
            )

            processed_urls = {default_pokemon_url}
            all_form_urls = {form["url"] for form in default_pokemon_data.get("forms", [])}
            variety_form_urls = set()

            for variety in varieties:
                if variety["pokemon"]["url"] in processed_urls:
                    continue

                pokemon_data = self.api_client.get(variety["pokemon"]["url"])
                form_ref_url = pokemon_data.get("forms", [{}])[0].get("url")
                if form_ref_url:
                    variety_form_urls.add(form_ref_url)

                form_data = self.api_client.get(form_ref_url) if form_ref_url else {}
                if self._should_skip_form(form_data):
                    continue

                variant_data = copy.deepcopy(default_template)
                variant_base_data = self._build_base_pokemon_data(
                    pokemon_data, species_data, variety["pokemon"]["url"]
                )
                variant_data.update(variant_base_data)

                is_battle_only = form_data.get("is_battle_only", False)
                if is_battle_only:
                    output_key, summary_key = self.output_dir_key_transformation, "transformation"
                else:
                    output_key, summary_key = self.output_dir_key_variant, "variant"

                output_dir = self.config[output_key]
                os.makedirs(output_dir, exist_ok=True)
                file_path = os.path.join(output_dir, f"{variant_data['name']}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(variant_data, f, indent=4, ensure_ascii=False)
                summaries[summary_key].append(
                    {
                        "name": variant_data["name"],
                        "id": variant_data["id"],
                        "sprite": variant_data["sprites"].get("front_default"),
                    }
                )
                processed_urls.add(variety["pokemon"]["url"])

            for form_url in all_form_urls - variety_form_urls:
                form_data = self.api_client.get(form_url)

                if self._should_skip_form(form_data) or form_data.get("is_default"):
                    continue

                cosmetic_data = copy.deepcopy(default_template)
                cosmetic_data["name"] = form_data.get("name", default_template["name"])
                cosmetic_data["is_default"] = False

                form_sprites = form_data.get("sprites", {})
                if form_sprites:
                    cosmetic_data["sprites"]["front_default"] = form_sprites.get("front_default")
                    cosmetic_data["sprites"]["front_shiny"] = form_sprites.get("front_shiny")
                    cosmetic_data["sprites"]["back_default"] = form_sprites.get("back_default")
                    cosmetic_data["sprites"]["back_shiny"] = form_sprites.get("back_shiny")

                output_dir = self.config[self.output_dir_key_cosmetic]
                os.makedirs(output_dir, exist_ok=True)
                file_path = os.path.join(output_dir, f"{cosmetic_data['name']}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(cosmetic_data, f, indent=4, ensure_ascii=False)

                summaries["cosmetic"].append(
                    {
                        "name": cosmetic_data["name"],
                        "id": cosmetic_data["id"],
                        "sprite": cosmetic_data["sprites"].get("front_default"),
                    }
                )

            return summaries
        except Exception as e:
            if not species_name:
                species_name = item_ref.get("name", "unknown")
            return f"Parsing failed for {species_name}: {e}"
