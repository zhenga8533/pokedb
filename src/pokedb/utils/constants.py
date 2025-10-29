"""Constants used throughout the PokemonDB parser."""

# Roman numeral conversion limits
MAX_ROMAN_NUMERAL = 3999

# API limits
DEFAULT_API_LIMIT = 3000

# HTTP status codes for retry
SERVER_ERROR_CODES = [500, 502, 503, 504]

# Roman numeral mapping (from largest to smallest for greedy algorithm)
ROMAN_NUMERAL_MAP = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]
