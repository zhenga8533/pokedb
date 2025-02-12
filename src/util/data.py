import logging

from requests import Session

from util.logger import Logger


def session_request(session: Session, url: str, timeout: int, logger: Logger) -> object:
    """
    Wrapper around requests.Session.get that logs errors and returns None on failure.

    :param session: The shared session to use for requests.
    :param url: The URL to request.
    :param timeout: The timeout for requests.
    :param logger: The logger to use.
    :return: The response object or None on failure.
    """

    try:
        logger.log(logging.INFO, f"Requesting data from {url}.")
        response = session.get(url, timeout=timeout)
        if response.status_code != 200:
            logger.log(logging.ERROR, f"Failed to request {url}: {response.status_code}")
            return None
    except Exception as e:
        logger.log(logging.ERROR, f"Request failed for {url}: {e}")
        return None

    logger.log(logging.INFO, f"Received data from {url}.")
    return response
