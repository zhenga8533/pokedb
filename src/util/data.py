import requests


def request_data(url: str) -> dict:
    """
    Request data from the PokeAPI.

    :param url: The URL of the data.
    :return: The data from the URL.
    """

    while True:
        try:
            response = requests.get(url, timeout=10)
        except requests.exceptions.Timeout:
            continue  # Restart the loop on timeout
        except requests.exceptions.RequestException:
            continue

        if response.status_code != 200:
            return None
        return response.json()
