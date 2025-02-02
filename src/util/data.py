from util.logger import Logger
import logging
import requests
import threading
import time


def request_data(url: str, timeout: int, stop_event: threading.Event, logger: Logger) -> dict:
    """
    Request data from the PokeAPI (or any API).

    :param url: The URL of the data.
    :param timeout: Request timeout in seconds.
    :param stop_event: The event to signal when the worker should stop.
    :param logger: The logger to log messages.
    :return: The JSON data from the URL, or None if unsuccessful.
    """

    attempt = 0

    while not stop_event.is_set():
        attempt += 1
        logger.log(logging.INFO, f'Requesting data from "{url}" (attempt {attempt}).')

        try:
            response = requests.get(url, timeout=timeout)
        except KeyboardInterrupt:
            # Re-raise KeyboardInterrupt to allow the program to stop immediately.
            raise
        except requests.exceptions.Timeout:
            # Log the timeout and retry the request.
            logger.log(logging.ERROR, f'Request to "{url}" timed out.')
            time.sleep(1)
            continue
        except requests.exceptions.RequestException:
            # Log the exception and retry.
            logger.log(logging.ERROR, f'Request to "{url}" failed.')
            time.sleep(1)
            continue

        # Check the status code of the response.
        status = response.status_code
        if status != 200:
            logger.log(logging.ERROR, f'Failed to request data from "{url}": {status}.')
            return None
        return response.json()

    logger.log(logging.INFO, f'Stopped request to "{url}" after {attempt} attempts.')
    return None
