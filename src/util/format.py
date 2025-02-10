def roman_to_int(s: str) -> int:
    """
    Convert a Roman numeral to an integer.

    :param s: The Roman numeral to convert.
    :return: The integer value of the Roman numeral.
    """

    roman_values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

    total = 0
    prev_value = 0

    for char in reversed(s.upper()):  # Process from right to left
        current_value = roman_values[char]
        if current_value < prev_value:
            total -= current_value  # Subtract if a smaller numeral precedes a larger one
        else:
            total += current_value
        prev_value = current_value

    return total
