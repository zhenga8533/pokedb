"""Text parsing and transformation utilities."""

import re
from typing import Any, Dict, List, Optional

from .constants import MAX_ROMAN_NUMERAL, ROMAN_NUMERAL_MAP


def parse_gen_range(generation_text: str) -> Optional[List[int]]:
    """
    Parses a generation string like 'Generations 3-6' into a list of generation numbers.

    Args:
        generation_text: A string containing generation information (e.g., "Generation 5", "Generations 3-6")

    Returns:
        A list of generation numbers, or None if the text cannot be parsed

    Examples:
        >>> parse_gen_range("Generation 5")
        [5]
        >>> parse_gen_range("Generations 3-6")
        [3, 4, 5, 6]
    """
    normalized_text = generation_text.lower()
    if "generation" in normalized_text:
        numbers = re.findall(r"\d+", normalized_text)
        if len(numbers) == 1:
            return [int(numbers[0])]
        if len(numbers) == 2:
            return list(range(int(numbers[0]), int(numbers[1]) + 1))
    return None


def int_to_roman(num: int) -> str:
    """
    Converts an integer to a Roman numeral using the subtractive notation.

    Args:
        num: An integer between 1 and 3999 (inclusive)

    Returns:
        The Roman numeral representation as a string

    Raises:
        ValueError: If num is not an integer or is outside the valid range

    Examples:
        >>> int_to_roman(4)
        'IV'
        >>> int_to_roman(1994)
        'MCMXCIV'
    """
    if not isinstance(num, int) or not 0 < num <= MAX_ROMAN_NUMERAL:
        raise ValueError(f"Input must be an integer between 1 and {MAX_ROMAN_NUMERAL}.")

    roman_numeral = []
    for value, numeral in ROMAN_NUMERAL_MAP:
        count, num = divmod(num, value)
        roman_numeral.append(numeral * count)

    return "".join(roman_numeral)


def _get_all_english_entries_generic(
    entries: List[Dict[str, Any]],
    key_name: str,
    field_name: str,
    target_set: set,
) -> Dict[str, str]:
    """
    Generic helper to find and clean all unique English entries from API data.

    This function maps entries to their field value (version_group or version),
    normalizing whitespace in the text content.

    Args:
        entries: List of entry dictionaries from the API
        key_name: The key in each entry containing the text to extract
        field_name: The field to use for categorization (e.g., 'version_group', 'version')
        target_set: Set of field values to filter for (only include these)

    Returns:
        A dictionary mapping field values to their cleaned English text
    """
    texts: Dict[str, str] = {}

    for entry in entries:
        field_value = entry.get(field_name, {}).get("name")

        # Only process English entries that match our target set
        if entry.get("language", {}).get("name") == "en" and field_value in target_set:
            cleaned_text = " ".join(entry.get(key_name, "").split())

            # Store only the first occurrence for each field value
            if cleaned_text and field_value not in texts:
                texts[field_value] = cleaned_text

    return texts


def get_all_english_entries_for_gen_by_game(
    entries: List[Dict[str, Any]],
    key_name: str,
    generation_version_groups: Optional[Dict[int, List[str]]] = None,
    target_gen: Optional[int] = None,
) -> Dict[str, str]:
    """
    Finds and cleans all unique English entries for a specific generation, organized by version group.

    Args:
        entries: List of entry dictionaries from the API (e.g., flavor_text_entries)
        key_name: The key containing the text to extract (e.g., 'flavor_text', 'effect')
        generation_version_groups: Mapping of generation numbers to version group lists
        target_gen: The target generation number to filter entries for

    Returns:
        A dictionary mapping version group names to their cleaned English text,
        or an empty dict if parameters are missing or no matches are found
    """
    if not entries or not generation_version_groups or target_gen is None:
        return {}

    target_version_groups = generation_version_groups.get(target_gen, [])
    if not target_version_groups:
        return {}

    return _get_all_english_entries_generic(
        entries, key_name, "version_group", set(target_version_groups)
    )


def get_all_english_entries_by_version(
    entries: List[Dict[str, Any]],
    key_name: str,
    target_versions: Optional[set] = None,
) -> Dict[str, str]:
    """
    Finds and cleans all unique English entries for specific game versions.

    This function is designed for API entries that use 'version' rather than
    'version_group' (e.g., flavor_text_entries for species).

    Args:
        entries: List of entry dictionaries from the API
        key_name: The key containing the text to extract (e.g., 'flavor_text')
        target_versions: Set of version names to filter for (e.g., {'red', 'blue'})

    Returns:
        A dictionary mapping version names to their cleaned English text,
        or an empty dict if parameters are missing
    """
    if not entries or not target_versions:
        return {}

    return _get_all_english_entries_generic(
        entries, key_name, "version", target_versions
    )


def build_version_group_to_generation_map(
    generation_version_groups: Dict[int, List[str]],
) -> Dict[str, int]:
    """
    Creates a mapping from version group names to their generation numbers.

    Args:
        generation_version_groups: Dict mapping generation numbers to lists of version groups

    Returns:
        Dict mapping version group names to generation numbers
    """
    return {
        version_group_name: gen_num
        for gen_num, version_group_list in generation_version_groups.items()
        for version_group_name in version_group_list
    }


def get_english_entry(
    entries: List[Dict[str, Any]],
    key_name: str,
    generation_version_groups: Optional[Dict[int, List[str]]] = None,
    target_gen: Optional[int] = None,
) -> Optional[str]:
    """
    Finds and cleans the most appropriate English entry from multilingual API entries.

    When generation information is provided, this function prioritizes entries from
    newer version groups within the target generation, searching backwards through
    generations if needed.

    Args:
        entries: List of entry dictionaries from the API
        key_name: The key containing the text to extract
        generation_version_groups: Optional mapping of generation numbers to version groups
        target_gen: Optional target generation number for prioritization

    Returns:
        The cleaned English text, or None if no English entry is found
    """
    if not entries:
        return None

    # If we have version group information, prioritize by generation
    if (
        entries
        and "version_group" in entries[0]
        and generation_version_groups
        and target_gen
    ):
        # Build priority list: newest version groups in target gen first, then work backwards
        all_version_groups: List[str] = []
        for generation in range(target_gen, 0, -1):
            all_version_groups.extend(
                reversed(generation_version_groups.get(generation, []))
            )

        # Map version groups to their English entries
        entry_map: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            if entry.get("language", {}).get("name") == "en":
                version_group_name = entry.get("version_group", {}).get("name")
                if version_group_name:
                    entry_map[version_group_name] = entry

        # Return the first match in priority order
        for version_group_name in all_version_groups:
            if version_group_name in entry_map:
                return " ".join(entry_map[version_group_name][key_name].split())

    # Fallback: return the first English entry found
    for entry in entries:
        if entry.get("language", {}).get("name") == "en":
            return " ".join(entry[key_name].split())

    return None


def kebab_to_snake(text: str) -> str:
    """
    Converts a kebab-case string to snake_case.

    Args:
        text: A string in kebab-case format (e.g., 'some-variable-name')

    Returns:
        The same string in snake_case format (e.g., 'some_variable_name')

    Examples:
        >>> kebab_to_snake('base-experience')
        'base_experience'
        >>> kebab_to_snake('special-attack')
        'special_attack'
    """
    return text.replace("-", "_")


def transform_keys_to_snake_case(data: Any) -> Any:
    """
    Recursively transforms all dictionary keys from kebab-case to snake_case.

    This function traverses nested data structures (dicts and lists) and converts
    all dictionary keys from kebab-case to snake_case for Python naming conventions.

    Args:
        data: Can be a dict, list, or any other type. Dicts and lists are traversed
              recursively, other types are returned unchanged.

    Returns:
        The transformed data structure with all dict keys converted to snake_case

    Examples:
        >>> transform_keys_to_snake_case({'some-key': 'value'})
        {'some_key': 'value'}
        >>> transform_keys_to_snake_case([{'nested-key': 'value'}])
        [{'nested_key': 'value'}]
    """
    if isinstance(data, dict):
        return {
            kebab_to_snake(key): transform_keys_to_snake_case(value)
            for key, value in data.items()
        }
    elif isinstance(data, list):
        return [transform_keys_to_snake_case(item) for item in data]
    else:
        return data
