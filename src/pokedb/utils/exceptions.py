"""Domain-specific exceptions raised by PokéDB."""


class PokeDBError(Exception):
    """Base exception for all PokéDB errors."""


class GenerationNotFoundError(PokeDBError):
    """Raised when a generation cannot be found or determined."""


class PokedexMappingError(PokeDBError):
    """Raised when a Pokédex mapping cannot be created."""


class ConfigurationError(PokeDBError):
    """Raised when configuration is invalid or cannot be loaded."""


class ParserExecutionError(PokeDBError):
    """Raised when one or more resources cannot be parsed completely."""


class DataValidationError(PokeDBError):
    """Raised when generated data violates the published data contract."""
