"""Domain-specific exceptions raised by PokéDB."""


class PokemonDBError(Exception):
    """Base exception for all PokéDB errors."""


class GenerationNotFoundError(PokemonDBError):
    """Raised when a generation cannot be found or determined."""


class PokedexMappingError(PokemonDBError):
    """Raised when a Pokédex mapping cannot be created."""


class ConfigurationError(PokemonDBError):
    """Raised when configuration is invalid or cannot be loaded."""


class ParserExecutionError(PokemonDBError):
    """Raised when one or more resources cannot be parsed completely."""


class DataValidationError(PokemonDBError):
    """Raised when generated data violates the published data contract."""


class ScraperError(PokemonDBError):
    """Raised when historical data cannot be fetched or parsed reliably."""
