"""Custom exceptions for the PokemonDB parser."""


class PokemonDBError(Exception):
    """Base exception for all PokemonDB errors."""

    pass


class GenerationNotFoundError(PokemonDBError):
    """Raised when a generation cannot be found or determined."""

    pass


class PokedexMappingError(PokemonDBError):
    """Raised when Pokédex mapping cannot be created."""

    pass


class ConfigurationError(PokemonDBError):
    """Raised when configuration is invalid or cannot be loaded."""

    pass
