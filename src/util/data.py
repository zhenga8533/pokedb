import requests


def request_data(url: str, timeout: int) -> dict:
    """
    Request data from the PokeAPI.

    :param url: The URL of the data.
    :param timeout: Request timeout in seconds.
    :return: The JSON data from the URL, or None if unsuccessful.
    """
    attempts = 0

    while attempts < 3:
        attempts += 1
        try:
            response = requests.get(url, timeout=timeout)
        except KeyboardInterrupt:
            raise
        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.RequestException:
            continue

        if response.status_code != 200:
            return None
        return response.json()

    return None
