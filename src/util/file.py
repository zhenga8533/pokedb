from util.logger import Logger
import logging
import os


def save(file_path: str, content: str, logger: Logger) -> None:
    """
    Save the content to a file.

    :param file_path: The path to the file.
    :param content: The content to save
    :param logger: The logger to log the result.
    :return: None
    """

    dir_path = file_path.rsplit("/", 1)[0]
    if not os.path.exists(dir_path):
        logger.log(logging.INFO, f"Creating {dir_path}...")
        os.makedirs(dir_path)

    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
            logger.log(logging.INFO, f"{file_path} was saved successfully.")
    except Exception as e:
        logger.log(logging.ERROR, f"An error occurred while saving to {file_path}: {e}")
        exit(1)


def load(file_path: str, logger: Logger) -> str:
    """
    Load the content of a file.

    :param file_path: The path to the file.
    :param logger: The logger to log the result.
    :return: The content of the file.
    """

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()
            logger.log(logging.INFO, f"{file_path} was loaded successfully.")
            return content
    except FileNotFoundError:
        logger.log(logging.ERROR, f"{file_path} was not found.")
        exit(1)
    except Exception as e:
        logger.log(logging.ERROR, f"An error occurred while loading {file_path}: {e}")
        exit(1)
