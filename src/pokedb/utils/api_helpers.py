"""Helper functions for API interactions."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from ..api_client import ApiClient

from .exceptions import GenerationNotFoundError, PokedexMappingError

logger = logging.getLogger(__name__)


def get_latest_generation(api_client: ApiClient, config: Dict[str, Any]) -> int:
    """
    Finds the latest Pokémon generation number by querying the API.

    Args:
        api_client: The API client instance to use for requests
        config: Configuration dictionary containing API settings

    Returns:
        The latest generation number as an integer

    Raises:
        GenerationNotFoundError: If generation data cannot be retrieved or parsed
    """
    logger.info("Determining the latest Pokémon generation...")
    try:
        data = api_client.get(f"{config['api_base_url']}generation/")
        generations = data.get("results", [])

        if not generations:
            raise GenerationNotFoundError("No generations found in API response.")

        latest_gen_num = max(
            int(generation["url"].split("/")[-2]) for generation in generations
        )
        logger.info(f"Latest generation found: {latest_gen_num}")
        return latest_gen_num

    except (KeyError, ValueError, IndexError) as e:
        raise GenerationNotFoundError(f"Failed to parse generation data: {e}")
    except Exception as e:
        raise GenerationNotFoundError(f"Could not determine latest generation: {e}")


def get_generation_dex_map(
    api_client: ApiClient, config: Dict[str, Any]
) -> Dict[int, str]:
    """
    Fetches all Pokédexes and creates a map of generation number to regional dex name.

    Args:
        api_client: The API client instance to use for requests
        config: Configuration dictionary containing API settings

    Returns:
        A dictionary mapping generation numbers to their main regional Pokédex names

    Raises:
        PokedexMappingError: If Pokédex data cannot be retrieved or mapped
    """
    logger.info("Fetching Pokédex information...")
    dex_map: Dict[int, str] = {}

    try:
        pokedex_list = api_client.get(f"{config['api_base_url']}pokedex?limit=100").get(
            "results", []
        )

        if not pokedex_list:
            raise PokedexMappingError("No Pokédexes found in API response.")

        for pokedex_ref in pokedex_list:
            dex_data = api_client.get(pokedex_ref["url"])

            # Only consider main series Pokédexes with version groups
            if dex_data.get("is_main_series") and dex_data.get("version_groups"):
                version_group_data = api_client.get(
                    dex_data["version_groups"][0]["url"]
                )
                generation_num = int(
                    version_group_data["generation"]["url"].split("/")[-2]
                )

                # Use the first main series dex for each generation
                if generation_num not in dex_map:
                    dex_map[generation_num] = dex_data["name"]

        logger.info(f"Successfully created Pokédex map with {len(dex_map)} entries.")
        return dex_map

    except (KeyError, ValueError, IndexError) as e:
        raise PokedexMappingError(f"Failed to parse Pokédex data: {e}")
    except Exception as e:
        raise PokedexMappingError(f"Could not create Pokédex map: {e}")
