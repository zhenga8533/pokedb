import requests


def request_data(url: str, timeout: int = 10) -> dict:
    """
    Request data from the PokeAPI.

    :param url: The URL of the data.
    :return: The data from the URL.
    """

    attempts = 0

    while True:
        attempts += 1
        if attempts > 5:
            return None

        try:
            response = requests.get(url, timeout=timeout)
        except requests.exceptions.Timeout:
            continue  # Restart the loop on timeout
        except requests.exceptions.RequestException:
            continue

        if response.status_code != 200:
            return None
        return response.json()
