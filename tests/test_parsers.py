import pytest

from pokedb.config import load_config
from pokedb.parsers.ability import AbilityParser
from pokedb.parsers.base import BaseParser
from pokedb.parsers.move import MoveParser
from pokedb.parsers.pokemon import PokemonParser
from pokedb.utils.exceptions import ParserExecutionError


class FailingParser(BaseParser):
    def __init__(self):
        super().__init__(load_config(), api_client=None)
        self.entity_type = "Test"
        self.api_endpoint = "test"

    def _get_all_item_refs(self):
        return [{"name": "broken", "url": "https://example.invalid/broken"}]

    def process(self, resource_ref):
        return f"Parsing failed for {resource_ref['name']}"


def test_parser_errors_fail_the_run():
    with pytest.raises(ParserExecutionError):
        FailingParser().run()


def test_move_history_uses_nearest_future_change_per_field():
    parser = MoveParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={
            5: ["black-white"],
            6: ["x-y"],
            8: ["sword-shield"],
        },
        target_gen=5,
    )
    cleaned_data = {
        "accuracy": 100,
        "power": 120,
        "pp": 5,
        "effect_chance": None,
        "type": "normal",
        "effect": "current",
        "short_effect": "current",
    }
    past_values = [
        {"version_group": {"name": "x-y"}, "power": 80},
        {
            "version_group": {"name": "sword-shield"},
            "power": 100,
            "pp": 10,
        },
    ]

    parser._apply_past_values(cleaned_data, past_values)

    assert cleaned_data["power"]["black-white"] == 80
    assert cleaned_data["pp"]["black-white"] == 10


def test_ability_history_uses_nearest_future_change():
    parser = AbilityParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={
            4: ["diamond-pearl"],
            5: ["black-white"],
            9: ["scarlet-violet"],
        },
        target_gen=4,
    )
    data = {
        "effect_entries": [
            {
                "language": {"name": "en"},
                "effect": "Current effect",
                "short_effect": "Current short effect",
            }
        ],
        "effect_changes": [
            {
                "version_group": {"name": "black-white"},
                "effect_entries": [
                    {
                        "language": {"name": "en"},
                        "effect": "Previous effect",
                    }
                ],
            }
        ],
    }

    effects, short_effects = parser._get_effects_for_target_generation(data)

    assert effects == {"diamond-pearl": "Previous effect"}
    assert short_effects == {"diamond-pearl": "Current short effect"}


def test_ability_effects_always_use_version_group_maps():
    parser = AbilityParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={9: ["scarlet-violet", "the-teal-mask"]},
        target_gen=9,
    )
    data = {
        "effect_entries": [
            {
                "language": {"name": "en"},
                "effect": "Current effect",
                "short_effect": "Current short effect",
            }
        ],
        "effect_changes": [],
    }

    effects, short_effects = parser._get_effects_for_target_generation(data)

    assert effects == {
        "scarlet-violet": "Current effect",
        "the-teal-mask": "Current effect",
    }
    assert set(short_effects) == {"scarlet-violet", "the-teal-mask"}


def test_pokemon_specific_data_comes_from_each_variety():
    parser = PokemonParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={9: ["scarlet-violet"]},
        target_gen=9,
        generation_dex_map={},
        target_versions={"scarlet"},
    )
    pokemon_data = {
        "base_experience": 182,
        "held_items": [],
        "moves": [
            {
                "move": {"name": "hydro-pump"},
                "version_group_details": [
                    {
                        "version_group": {"name": "scarlet-violet"},
                        "move_learn_method": {"name": "level-up"},
                        "level_learned_at": 1,
                    }
                ],
            }
        ],
    }

    result = parser._get_pokemon_specific_data(pokemon_data)

    assert result["base_experience"] == 182
    assert result["moves"]["level-up"][0]["name"] == "hydro-pump"


def test_structured_pokeapi_history_is_applied_before_scraped_history():
    parser = PokemonParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={1: ["red-blue"]},
        target_gen=1,
        generation_dex_map={},
    )
    cleaned_data = {
        "types": ["electric", "steel"],
        "abilities": [
            {"name": "magnet-pull", "is_hidden": False, "slot": 1},
            {"name": "sturdy", "is_hidden": False, "slot": 2},
        ],
        "stats": {
            "hp": 25,
            "attack": 35,
            "defense": 70,
            "special-attack": 95,
            "special-defense": 55,
            "speed": 45,
        },
        "ev_yield": [{"stat": "special-attack", "effort": 1}],
    }
    pokemon_data = {
        "past_types": [
            {
                "generation": {"url": "https://example.test/generation/1/"},
                "types": [{"slot": 1, "type": {"name": "electric"}}],
            }
        ],
        "past_abilities": [
            {
                "generation": {"url": "https://example.test/generation/3/"},
                "abilities": [
                    {"ability": None, "is_hidden": False, "slot": 2}
                ],
            }
        ],
        "past_stats": [
            {
                "generation": {"url": "https://example.test/generation/1/"},
                "stats": [
                    {
                        "base_stat": 95,
                        "effort": 0,
                        "stat": {"name": "special"},
                    }
                ],
            }
        ],
    }

    parser._apply_pokeapi_past_values(cleaned_data, pokemon_data)

    assert cleaned_data["types"] == ["electric"]
    assert cleaned_data["abilities"] == []
    assert cleaned_data["ev_yield"] == []
    assert cleaned_data["stats"] == {
        "hp": 25,
        "attack": 35,
        "defense": 70,
        "special": 95,
        "speed": 45,
    }


def test_structured_pokeapi_past_ability_replaces_current_ability():
    parser = PokemonParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={6: ["x-y"]},
        target_gen=6,
        generation_dex_map={},
    )
    cleaned_data = {
        "types": ["ghost", "poison"],
        "abilities": [
            {"name": "cursed-body", "is_hidden": False, "slot": 1}
        ],
        "stats": {},
        "ev_yield": [],
    }
    pokemon_data = {
        "past_types": [],
        "past_stats": [],
        "past_abilities": [
            {
                "generation": {"url": "https://example.test/generation/6/"},
                "abilities": [
                    {
                        "ability": {"name": "levitate"},
                        "is_hidden": False,
                        "slot": 1,
                    }
                ],
            }
        ],
    }

    parser._apply_pokeapi_past_values(cleaned_data, pokemon_data)

    assert cleaned_data["abilities"][0]["name"] == "levitate"


def test_scraped_single_ability_does_not_create_a_second_slot():
    parser = PokemonParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={6: ["x-y"]},
        target_gen=6,
        generation_dex_map={},
        scraper_func=lambda name: {
            "changes": [
                {"generations": [3, 4, 5, 6], "change": {"ability": "levitate"}}
            ]
        },
    )
    cleaned_data = {
        "species": "gengar",
        "abilities": [
            {"name": "cursed-body", "is_hidden": False, "slot": 1}
        ],
        "stats": {},
        "types": ["ghost", "poison"],
    }

    parser._apply_historical_changes(cleaned_data)

    assert cleaned_data["abilities"] == [
        {"name": "levitate", "is_hidden": False, "slot": 1}
    ]


def test_form_names_are_matched_across_source_naming_conventions():
    parser = PokemonParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={7: ["sun-moon"]},
        target_gen=7,
        generation_dex_map={},
    )

    assert parser._form_names_match(
        "Red-Striped Form", "Red-Striped Basculin", "basculin"
    )
    assert parser._form_names_match(
        "Average Size", "Average Gourgeist", "gourgeist"
    )
    assert parser._form_names_match("Heat Rotom", "Heat Rotom", "rotom")
    assert not parser._form_names_match(
        "Blue-Striped Form", "Red-Striped Basculin", "basculin"
    )


def test_evolution_details_preserve_each_condition():
    chain_url = "https://example.test/evolution-chain/1"
    species_url = "https://example.test/pokemon-species/vaporeon"
    responses = {
        chain_url: {
            "chain": {
                "species": {"name": "eevee"},
                "evolves_to": [
                    {
                        "species": {"name": "vaporeon", "url": species_url},
                        "evolution_details": [
                            {
                                "item": {"name": "water-stone"},
                                "trigger": {"name": "use-item"},
                            },
                            {
                                "location": {"name": "special-location"},
                                "trigger": {"name": "level-up"},
                            },
                        ],
                        "evolves_to": [],
                    }
                ],
            }
        },
        species_url: {"generation": {"url": "https://example.test/generation/1/"}},
    }

    class FakeApiClient:
        def get(self, url):
            return responses[url]

    parser = PokemonParser(
        config=load_config(),
        api_client=FakeApiClient(),
        generation_version_groups={},
        target_gen=9,
        generation_dex_map={},
    )
    chain = parser._get_evolution_chain(chain_url)
    details = chain["evolves_to"][0]["evolution_details"]

    assert len(details) == 2
    assert details[0]["item"] == "water-stone"
    assert details[1]["location"] == "special-location"


def test_evolution_details_use_latest_method_for_target_generation():
    parser = PokemonParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={
            4: ["diamond-pearl"],
            5: ["black-white"],
            6: ["x-y", "omega-ruby-alpha-sapphire"],
            8: ["sword-shield"],
            9: ["scarlet-violet", "the-teal-mask"],
        },
        target_gen=9,
        generation_dex_map={},
    )
    details = [
        {
            "trigger": {"name": "level-up"},
            "location": {"name": "sinnoh-route-217"},
            "near_special_rock": True,
            "version_group": {"name": "diamond-pearl"},
        },
        {
            "trigger": {"name": "use-item"},
            "item": {"name": "ice-stone"},
            "version_group": {"name": "sword-shield"},
        },
    ]

    result = parser._get_evolution_details_for_target(details)

    assert len(result) == 1
    assert result[0]["item"] == "ice-stone"
    assert result[0]["location"] is None
    assert result[0]["introduced_in_version_group"] == "sword-shield"
    assert result[0]["version_groups"] == ["scarlet-violet", "the-teal-mask"]


def test_evolution_details_can_differ_within_one_generation():
    parser = PokemonParser(
        config=load_config(),
        api_client=None,
        generation_version_groups={
            4: ["diamond-pearl"],
            6: ["x-y", "omega-ruby-alpha-sapphire"],
        },
        target_gen=6,
        generation_dex_map={},
    )
    details = [
        {
            "trigger": {"name": "level-up"},
            "location": {"name": "eterna-forest"},
            "version_group": {"name": "diamond-pearl"},
        },
        {
            "trigger": {"name": "level-up"},
            "location": {"name": "kalos-route-20"},
            "version_group": {"name": "x-y"},
        },
        {
            "trigger": {"name": "level-up"},
            "location": {"name": "petalburg-woods"},
            "version_group": {"name": "omega-ruby-alpha-sapphire"},
        },
    ]

    result = parser._get_evolution_details_for_target(details)

    assert [(entry["location"], entry["version_groups"]) for entry in result] == [
        ("kalos-route-20", ["x-y"]),
        ("petalburg-woods", ["omega-ruby-alpha-sapphire"]),
    ]


def test_location_evolution_excludes_games_without_that_region():
    location_url = "https://example.test/location/route-217"

    class FakeApiClient:
        def get(self, url):
            responses = {
                "https://pokeapi.co/api/v2/version-group/diamond-pearl": {
                    "regions": [{"name": "sinnoh"}]
                },
                "https://pokeapi.co/api/v2/version-group/platinum": {
                    "regions": [{"name": "sinnoh"}]
                },
                "https://pokeapi.co/api/v2/version-group/heartgold-soulsilver": {
                    "regions": [{"name": "kanto"}, {"name": "johto"}]
                },
                location_url: {"region": {"name": "sinnoh"}},
            }
            return responses[url]

    parser = PokemonParser(
        config=load_config(),
        api_client=FakeApiClient(),
        generation_version_groups={
            4: ["diamond-pearl", "platinum", "heartgold-soulsilver"]
        },
        target_gen=4,
        generation_dex_map={},
    )
    details = [
        {
            "trigger": {"name": "level-up"},
            "location": {"name": "sinnoh-route-217", "url": location_url},
            "version_group": {"name": "diamond-pearl"},
        }
    ]

    result = parser._get_evolution_details_for_target(details)

    assert result[0]["version_groups"] == ["diamond-pearl", "platinum"]
