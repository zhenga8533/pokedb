import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter, Retry
from tqdm import tqdm


def load_config():
    """Loads settings from the root config.json file."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
    with open(config_path, "r") as f:
        return json.load(f)


def setup_session(config):
    """Creates a requests Session with automatic retry logic."""
    session = requests.Session()
    retries = Retry(total=config["max_retries"], backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def get_latest_generation(session, config):
    """Finds the latest Pokémon generation number by querying the API."""
    print("Determining the latest Pokémon generation...")
    try:
        response = session.get(f"{config['api_base_url']}generation/", timeout=config["timeout"])
        response.raise_for_status()
        generations = response.json()["results"]
        latest_gen_num = max(int(g["url"].split("/")[-2]) for g in generations)
        print(f"Latest generation found: {latest_gen_num}")
        return latest_gen_num
    except Exception as e:
        print(f"Could not determine latest generation. Defaulting to 9. Error: {e}")
        return 9  # Fallback to a sensible default


def get_english_entry(entries, key_name):
    """Finds and cleans the English entry from a list of multilingual API entries."""
    if not entries:
        return None
    for entry in entries:
        if entry.get("language", {}).get("name") == "en":
            return " ".join(entry[key_name].split())
    return None


def run_parser(parser_config):
    """A generic runner for fetching and processing a list of items concurrently."""
    item_name = parser_config["item_name"]
    master_list_url = parser_config["master_list_url"]
    processing_func = parser_config["processing_func"]
    session = parser_config["session"]
    config = parser_config["config"]

    print(f"Fetching master list of {item_name.lower()}s...")
    try:
        response = session.get(master_list_url, timeout=config["timeout"])
        response.raise_for_status()
        all_items = response.json()["results"]
    except requests.exceptions.RequestException as e:
        print(f"Fatal: Could not fetch {item_name.lower()} list. {e}")
        return

    print(f"Found {len(all_items)} {item_name.lower()}s. Starting concurrent processing...")

    errors = []
    with ThreadPoolExecutor(max_workers=config["max_workers"]) as executor:
        future_map = {executor.submit(processing_func, item, session, config): item for item in all_items}

        for future in tqdm(as_completed(future_map), total=len(all_items), desc=f"Processing {item_name}s"):
            result = future.result()
            if result:
                errors.append(result)

    print(f"\n{item_name} processing complete.")
    if errors:
        print("\nThe following errors occurred:")
        for error in errors:
            print(f"- {error}")
    else:
        output_dir_key = f"output_dir_{item_name.lower()}"
        output_path = config[output_dir_key]
        print(f"All {item_name.lower()}s successfully parsed and saved to '{os.path.abspath(output_path)}'.")


def git_push_data():
    """Commits and pushes the 'data' directory to the 'data' branch."""
    print("\nAttempting to push data to the 'data' branch...")
    try:
        original_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip().decode("utf-8")

        try:
            subprocess.check_call(["git", "rev-parse", "--verify", "data"])
            subprocess.check_call(["git", "switch", "data"])
        except subprocess.CalledProcessError:
            print("Creating 'data' branch as it does not exist.")
            subprocess.check_call(["git", "switch", "-c", "data"])

        subprocess.check_call(["git", "add", "data/"])

        status_output = subprocess.check_output(["git", "status", "--porcelain", "data/"]).strip()
        if not status_output:
            print("No data changes to commit.")
        else:
            commit_message = f"Data update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.check_call(["git", "commit", "-m", commit_message])
            print("Pushing to origin/data...")
            subprocess.check_call(["git", "push", "origin", "data"])
            print("Data pushed successfully.")

        subprocess.check_call(["git", "switch", original_branch])
        print(f"Switched back to '{original_branch}' branch.")

    except subprocess.CalledProcessError as e:
        print(f"An error occurred during Git operations: {e}")
        print("Please ensure Git is installed, the repository is initialized, and you are authenticated.")
    except FileNotFoundError:
        print("Error: Git command not found. Please ensure Git is installed and in your system's PATH.")
