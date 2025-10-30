import copy
from logging import getLogger
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from ..api_client import ApiClient
from ..utils import (
    get_all_english_entries_by_version,
    get_english_entry,
    int_to_roman,
    write_json_file,
)
from .base import PokemonCategory
from .generation import GenerationParser

logger = getLogger(__name__)


class PokemonParser(GenerationParser):
    """
    A comprehensive parser for Pokémon species and all their forms/varieties.

    This is the most complex parser as it handles:
    - Default/primary Pokémon forms
    - Regional variants (e.g., Alolan, Galarian forms)
    - Battle-only transformations (e.g., Mega Evolution, Gigantamax)
    - Cosmetic forms (e.g., Unown letters, Spinda patterns)
    - Historical stat changes via web scraping
    - Evolution chains with generation filtering
    - Moves, held items, and sprites per generation

    The parser organizes output into four categories defined by PokemonCategory.
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
        scraper_func: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        super().__init__(
            config,
            api_client,
            generation_version_groups,
            target_gen,
            generation_dex_map,
        )
        self.entity_type = "Species"
        self.api_endpoint = "pokemon_species"
        self.output_dir_key_pokemon = "output_dir_pokemon"
        self.output_dir_key_variant = "output_dir_variant"
        self.output_dir_key_transformation = "output_dir_transformation"
        self.output_dir_key_cosmetic = "output_dir_cosmetic"
        self.is_historical = is_historical
        self.target_versions = target_versions or set()
        self.scraper_func = scraper_func

    def _apply_historical_changes(self, cleaned_data: Dict[str, Any]):
        """
        Applies scraped historical changes to Pokémon data for the target generation.

        The PokéAPI doesn't track all historical changes (especially Gen 1 stats),
        so this method uses web scraping from PokemonDB to get generation-specific
        data for abilities, stats, types, and other attributes.

        Args:
            cleaned_data: The Pokémon data dictionary to modify in-place

        Modifies:
            cleaned_data: Updates stats, abilities, types, and other fields based
                          on historical changes for the target generation
        """
        if not self.target_gen or not self.scraper_func:
            return

        logger.debug(f"Scraping historical changes for {cleaned_data['species']}")
        scraper_data = self.scraper_func(cleaned_data["species"])
        all_changes = scraper_data.get("changes", [])

        if not all_changes:
            return

        # Apply changes that occurred in the target generation
        for change_item in all_changes:
            generations = change_item.get("generations", [])
            change = change_item.get("change", {})

            if self.target_gen in generations:
                # Update non-hidden ability
                if "ability" in change:
                    for i, ability in enumerate(cleaned_data.get("abilities", [])):
                        if not ability.get("is_hidden"):
                            cleaned_data["abilities"][i]["name"] = change["ability"]
                            break

                # Update base stats
                if "stats" in change:
                    cleaned_data["stats"].update(change["stats"])

                # Update types
                if "types" in change:
                    cleaned_data["types"] = change["types"]

                # Update other attributes
                if "base_experience" in change:
                    cleaned_data["base_experience"] = change["base_experience"]
                if "base_happiness" in change:
                    cleaned_data["base_happiness"] = change["base_happiness"]
                if "capture_rate" in change:
                    cleaned_data["capture_rate"] = change["capture_rate"]
                if "ev_yield" in change:
                    cleaned_data["ev_yield"] = change["ev_yield"]

    def _get_evolution_chain(self, chain_url: str) -> Optional[Dict[str, Any]]:
        """
        Recursively fetches and processes an evolution chain, filtering future generations.

        Evolution chains are nested structures showing species → evolutions → further evolutions.
        This method filters out evolutions that don't exist in the target generation.

        Args:
            chain_url: API URL for the evolution chain endpoint

        Returns:
            A nested dictionary representing the evolution chain, or None if fetch fails.
            Structure: {
                "species_name": str,
                "evolves_to": [
                    {
                        "species_name": str,
                        "evolution_details": {...},
                        "evolves_to": [...]
                    }
                ]
            }
        """
        try:
            chain_data = self.api_client.get(chain_url)["chain"]

            def recurse_chain(chain: Dict[str, Any]) -> Dict[str, Any]:
                species_name = chain["species"]["name"]
                evolves_to: List[Dict[str, Any]] = []

                for evolution in chain.get("evolves_to", []):
                    # Check if this evolution is from a future generation
                    species_url = evolution["species"]["url"]
                    species_data = self.api_client.get(species_url)
                    evolution_gen = int(
                        species_data["generation"]["url"].split("/")[-2]
                    )

                    # Skip evolutions from future generations
                    if self.target_gen is not None and evolution_gen > self.target_gen:
                        logger.debug(
                            f"Skipping future evolution: {evolution['species']['name']} (Gen {evolution_gen})"
                        )
                        continue

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
                                "held_item": (details.get("held_item") or {}).get(
                                    "name"
                                ),
                                "known_move": (details.get("known_move") or {}).get(
                                    "name"
                                ),
                                "known_move_type": (
                                    details.get("known_move_type") or {}
                                ).get("name"),
                                "location": (details.get("location") or {}).get("name"),
                                "min_level": details.get("min_level"),
                                "min_happiness": details.get("min_happiness"),
                                "min_beauty": details.get("min_beauty"),
                                "min_affection": details.get("min_affection"),
                                "needs_overworld_rain": details.get(
                                    "needs_overworld_rain"
                                ),
                                "party_species": (
                                    details.get("party_species") or {}
                                ).get("name"),
                                "party_type": (details.get("party_type") or {}).get(
                                    "name"
                                ),
                                "relative_physical_stats": details.get(
                                    "relative_physical_stats"
                                ),
                                "time_of_day": details.get("time_of_day"),
                                "trade_species": (
                                    details.get("trade_species") or {}
                                ).get("name"),
                                "turn_upside_down": details.get("turn_upside_down"),
                            },
                            "evolves_to": next_evolution["evolves_to"],
                        }
                    )
                return {"species_name": species_name, "evolves_to": evolves_to}

            return recurse_chain(chain_data)
        except Exception as e:
            logger.warning(
                f"Could not process evolution chain from {chain_url}. Error: {e}"
            )
            return None

    def _get_generation_data(
        self,
        data: Dict[str, Any],
        key: str,
        name_key: str,
        details_key: str,
        version_key: str,
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
                        {
                            "name": move_name,
                            "level_learned_at": level,
                            "version_groups": sorted(list(games)),
                        }
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

    def _get_generation_pokedex_numbers(
        self, pokedex_numbers: List[Dict[str, Any]]
    ) -> Dict[str, int]:
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
        form_introduction_gen = int(
            version_group_data["generation"]["url"].split("/")[-2]
        )
        return self.target_gen is not None and form_introduction_gen > self.target_gen

    def _build_base_pokemon_data(
        self,
        pokemon_data: Dict[str, Any],
        species_data: Dict[str, Any],
        source_url: str,
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
                {
                    "name": a["ability"]["name"],
                    "is_hidden": a["is_hidden"],
                    "slot": a["slot"],
                }
                for a in pokemon_data.get("abilities", [])
            ],
            "stats": {
                s["stat"]["name"]: s["base_stat"] for s in pokemon_data.get("stats", [])
            },
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
                "forms_switchable": species_data.get("forms_switchable"),
                "order": species_data.get("order"),
                "growth_rate": species_data.get("growth_rate", {}).get("name"),
                "habitat": (
                    species_data.get("habitat", {}).get("name")
                    if species_data.get("habitat")
                    else None
                ),
                "evolves_from_species": (
                    species_data.get("evolves_from_species", {}).get("name")
                    if species_data.get("evolves_from_species")
                    else None
                ),
                "pokedex_numbers": self._get_generation_pokedex_numbers(
                    species_data.get("pokedex_numbers", [])
                ),
                "color": species_data.get("color", {}).get("name"),
                "shape": species_data.get("shape", {}).get("name"),
                "egg_groups": [
                    group["name"] for group in species_data.get("egg_groups", [])
                ],
                "flavor_text": get_all_english_entries_by_version(
                    species_data.get("flavor_text_entries", []),
                    "flavor_text",
                    self.target_versions,
                ),
                "genus": get_english_entry(species_data.get("genera", []), "genus"),
                "generation": species_data.get("generation", {}).get("name"),
                "evolution_chain": evolution_chain,
                "held_items": self._get_generation_data(
                    pokemon_data, "held_items", "item", "version_details", "version"
                ),
                "moves": self._get_generation_data(
                    pokemon_data,
                    "moves",
                    "move",
                    "version_group_details",
                    "version_group",
                ),
            }
        )

    def _collect_varieties_and_forms(
        self,
        species_data: Dict[str, Any],
        default_pokemon_data: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], Set[str]]:
        """
        Collects and categorizes all varieties and forms for a species.

        Args:
            species_data: The species API data
            default_pokemon_data: The default Pokemon's API data

        Returns:
            A tuple of (varieties, all_forms_in_gen, variety_form_urls):
            - varieties: List of variety dictionaries from the API
            - all_forms_in_gen: List of form names and categories in the target generation
            - variety_form_urls: Set of form URLs that belong to varieties
        """
        species_name = species_data["name"]
        varieties = species_data.get("varieties", [])

        # If no varieties, create default variety
        if not varieties:
            default_pokemon_url = (
                f"{self.config['api_base_url']}pokemon/{species_data['id']}"
            )
            default_variety = {
                "is_default": True,
                "pokemon": {"name": species_name, "url": default_pokemon_url},
            }
            varieties = [default_variety]

        all_forms_in_gen: List[Dict[str, str]] = []
        variety_form_urls: Set[str] = set()

        # Process varieties to categorize their forms
        for variety in varieties:
            pokemon_data = self.api_client.get(variety["pokemon"]["url"])

            # Skip varieties with no forms
            forms = pokemon_data.get("forms", [])
            if not forms:
                logger.info(
                    f"Skipping variety {pokemon_data['name']}: No forms found."
                )
                continue

            form_ref_url = forms[0].get("url") if forms else None
            if form_ref_url:
                variety_form_urls.add(form_ref_url)
                form_data = self.api_client.get(form_ref_url)
                if not self._should_skip_form(form_data):
                    category = "variant"
                    if variety.get("is_default"):
                        category = "default"
                    elif form_data.get("is_battle_only"):
                        category = "transformation"
                    all_forms_in_gen.append(
                        {"name": pokemon_data["name"], "category": category}
                    )

        # Process cosmetic forms (forms that don't have varieties)
        all_form_urls = {form["url"] for form in default_pokemon_data.get("forms", [])}
        for form_url in all_form_urls - variety_form_urls:
            form_data = self.api_client.get(form_url)
            if not self._should_skip_form(form_data) and not form_data.get(
                "is_default"
            ):
                all_forms_in_gen.append(
                    {"name": form_data.get("name", ""), "category": "cosmetic"}
                )

        all_forms_in_gen.sort(key=lambda x: x["name"])
        return varieties, all_forms_in_gen, variety_form_urls

    def _process_default_pokemon(
        self,
        default_variety: Dict[str, Any],
        default_pokemon_data: Dict[str, Any],
        species_data: Dict[str, Any],
        evolution_chain: Optional[Dict[str, Any]],
        all_forms_in_gen: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Processes the default/primary Pokemon form.

        Args:
            default_variety: The default variety from the API
            default_pokemon_data: The default Pokemon's API data
            species_data: The species API data
            evolution_chain: The evolution chain data
            all_forms_in_gen: List of all forms in the target generation

        Returns:
            The processed default Pokemon data dictionary
        """
        default_template = self._build_base_pokemon_data(
            default_pokemon_data, species_data, default_variety["pokemon"]["url"]
        )
        self._add_default_species_data(
            default_template, default_pokemon_data, species_data, evolution_chain
        )
        default_template["forms"] = all_forms_in_gen

        if self.is_historical:
            self._apply_historical_changes(default_template)

        output_dir = self.config[self.output_dir_key_pokemon]
        write_json_file(output_dir, default_template["name"], default_template)

        return default_template

    def _process_variety(
        self,
        variety: Dict[str, Any],
        species_data: Dict[str, Any],
        default_template: Dict[str, Any],
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Processes a single variety (variant or transformation).

        Args:
            variety: The variety data from the API
            species_data: The species API data
            default_template: The default Pokemon template to base this variety on

        Returns:
            A tuple of (category, summary_dict) or None if the variety should be skipped
        """
        pokemon_data = self.api_client.get(variety["pokemon"]["url"])

        # Skip varieties with no game indices
        if not pokemon_data.get("game_indices"):
            logger.info(
                f"Skipping variety {pokemon_data['name']}: No game indices found."
            )
            return None

        forms = pokemon_data.get("forms", [])
        form_ref_url = forms[0].get("url") if forms else None

        form_data = self.api_client.get(form_ref_url) if form_ref_url else {}
        if self._should_skip_form(form_data):
            return None

        # Create variant data by copying default and updating with variety-specific info
        variant_data = copy.deepcopy(default_template)
        variant_base_data = self._build_base_pokemon_data(
            pokemon_data, species_data, variety["pokemon"]["url"]
        )
        variant_data.update(variant_base_data)

        # Determine category and output directory
        is_battle_only = form_data.get("is_battle_only", False)
        if is_battle_only:
            output_key, summary_key = (
                self.output_dir_key_transformation,
                "transformation",
            )
        else:
            output_key, summary_key = self.output_dir_key_variant, "variant"

        # Write to file
        output_dir = self.config[output_key]
        write_json_file(output_dir, variant_data["name"], variant_data)

        # Return summary
        summary = {
            "name": variant_data["name"],
            "id": variant_data["id"],
            "sprite": variant_data["sprites"].get("front_default"),
        }
        return summary_key, summary

    def _process_cosmetic_form(
        self,
        form_url: str,
        default_template: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Processes a single cosmetic form.

        Args:
            form_url: The API URL for the form
            default_template: The default Pokemon template to base this form on

        Returns:
            A summary dictionary or None if the form should be skipped
        """
        form_data = self.api_client.get(form_url)

        if self._should_skip_form(form_data) or form_data.get("is_default"):
            return None

        # Create cosmetic data by copying default and updating sprites
        cosmetic_data = copy.deepcopy(default_template)
        cosmetic_data["name"] = form_data.get("name", default_template["name"])
        cosmetic_data["is_default"] = False

        form_sprites = form_data.get("sprites", {})
        if form_sprites:
            cosmetic_data["sprites"]["front_default"] = form_sprites.get(
                "front_default"
            )
            cosmetic_data["sprites"]["front_shiny"] = form_sprites.get("front_shiny")
            cosmetic_data["sprites"]["back_default"] = form_sprites.get("back_default")
            cosmetic_data["sprites"]["back_shiny"] = form_sprites.get("back_shiny")

        # Write to file
        output_dir = self.config[self.output_dir_key_cosmetic]
        write_json_file(output_dir, cosmetic_data["name"], cosmetic_data)

        # Return summary
        return {
            "name": cosmetic_data["name"],
            "id": cosmetic_data["id"],
            "sprite": cosmetic_data["sprites"].get("front_default"),
        }

    def process(
        self, resource_ref: Dict[str, str]
    ) -> Optional[Union[Dict[str, List[Dict[str, Any]]], str]]:
        """
        Processes a Pokémon species and all its varieties and forms.

        This method orchestrates the processing of:
        - Default Pokémon form with full species data
        - All regional variants and their differences
        - Battle-only transformations (Megas, Gigantamax, etc.)
        - Cosmetic forms (Unown, Spinda, etc.)

        Args:
            resource_ref: Dictionary with 'name' and 'url' for the species

        Returns:
            A dict with category keys mapping to lists of summary dicts,
            or an error string if processing fails
        """
        species_name = ""
        try:
            # Fetch species and evolution data
            species_data = self.api_client.get(resource_ref["url"])
            species_name = species_data["name"]
            evolution_chain_url = species_data.get("evolution_chain", {}).get("url")
            evolution_chain = (
                self._get_evolution_chain(evolution_chain_url)
                if evolution_chain_url
                else None
            )

            # Initialize summaries
            summaries: Dict[str, List[Dict[str, Any]]] = {
                "pokemon": [],
                "variant": [],
                "transformation": [],
                "cosmetic": [],
            }

            # Get default variety and its data
            varieties = species_data.get("varieties", [])
            if not varieties:
                default_pokemon_url = (
                    f"{self.config['api_base_url']}pokemon/{species_data['id']}"
                )
                default_variety = {
                    "is_default": True,
                    "pokemon": {"name": species_name, "url": default_pokemon_url},
                }
                varieties = [default_variety]

            default_variety = next(
                (v for v in varieties if v["is_default"]), varieties[0]
            )
            default_pokemon_data = self.api_client.get(
                default_variety["pokemon"]["url"]
            )

            # Skip species with no game indices (placeholder entries)
            if not default_pokemon_data.get("game_indices"):
                logger.info(
                    f"Skipping {species_name}: No game indices found in default pokemon data."
                )
                return None

            # Collect and categorize all varieties and forms
            varieties, all_forms_in_gen, variety_form_urls = (
                self._collect_varieties_and_forms(species_data, default_pokemon_data)
            )

            # Process default Pokemon
            default_template = self._process_default_pokemon(
                default_variety,
                default_pokemon_data,
                species_data,
                evolution_chain,
                all_forms_in_gen,
            )
            summaries["pokemon"].append(
                {
                    "name": default_template["name"],
                    "id": default_template["id"],
                    "sprite": default_template["sprites"].get("front_default"),
                }
            )

            # Process varieties (variants and transformations)
            processed_urls = {default_variety["pokemon"]["url"]}
            for variety in varieties:
                if variety["pokemon"]["url"] in processed_urls:
                    continue

                result = self._process_variety(variety, species_data, default_template)
                if result:
                    summary_key, summary = result
                    summaries[summary_key].append(summary)
                    processed_urls.add(variety["pokemon"]["url"])

            # Process cosmetic forms
            all_form_urls = {
                form["url"] for form in default_pokemon_data.get("forms", [])
            }
            for form_url in all_form_urls - variety_form_urls:
                summary = self._process_cosmetic_form(form_url, default_template)
                if summary:
                    summaries["cosmetic"].append(summary)

            return summaries
        except Exception as e:
            if not species_name:
                species_name = resource_ref.get("name", "unknown")
            logger.error(f"Unexpected error processing {species_name}: {e}")
            return f"Parsing failed for {species_name}: {e}"
