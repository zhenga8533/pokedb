# PokéAPI Parser

[![Update PokéAPI Data](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml/badge.svg)](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A Python-based tool designed to fetch, parse, and structure data from the [PokéAPI](https://pokeapi.co/). This project automates the process of collecting detailed information about Pokémon, their abilities, moves, items, and more, and saves it into a clean, easy-to-use JSON format.

The data is automatically updated weekly and pushed to the `data` branch, ensuring that you always have the latest information.

## Features

- **Comprehensive Data Parsing**: Extracts data for Pokémon (including all forms and varieties), abilities, items, and moves.
- **Concurrent Processing**: Utilizes a thread pool to fetch data from the API concurrently, significantly speeding up the parsing process.
- **Configuration-driven**: Easily configure settings like API endpoints, timeouts, and output directories through the `config.json` file.
- **Generation-specific Data**: Allows you to parse data up to a specific Pokémon generation.
- **Automated Data Updates**: Includes a GitHub Actions workflow to automatically update the data on a weekly basis, ensuring the dataset remains current.
- **Structured JSON Output**: Saves the parsed data in a well-structured and easy-to-navigate JSON format.

## How to Use

### Prerequisites

- Python 3.12 or higher

### Installation

1.  Clone the repository:

    ```bash
    git clone https://github.com/zhenga8533/pokeapi-parser.git
    cd pokeapi-parser
    ```

2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

### Running the Parsers

You can run all parsers at once or specify the ones you need.

- **Run all parsers**:

  ```bash
  python main.py --all
  ```

- **Run specific parsers**:
  You can specify one or more parsers to run by listing their names. The available parsers are `pokemon`, `ability`, `item`, and `move`.

  ```bash
  python main.py pokemon item
  ```

- **Parse data for a specific generation**:
  Use the `--gen` flag to parse all data up to a specific generation. The output will be placed in a folder corresponding to that generation (e.g., `output/gen3`).

  ```bash
  python main.py --all --gen 3
  ```

## Project Structure

```
.
├── .github/workflows/
│   └── update-data.yaml  # GitHub Actions workflow for automated data updates
├── output/                 # Default directory for generated JSON files
├── src/pokeapi_parser/
│   ├── parsers/            # Contains the logic for parsing different data types
│   │   ├── ability.py
│   │   ├── item.py
│   │   ├── move.py
│   │   └── pokemon.py
│   ├── __init__.py
│   ├── api_client.py       # Handles all requests to the PokéAPI
│   └── utils.py            # Utility functions
├── config.json             # Configuration file for the project
├── main.py                 # Main entry point for the application
└── requirements.txt        # Project dependencies
```

## Automated Data Updates

This project includes a GitHub Actions workflow defined in `.github/workflows/update-data.yaml`. This workflow runs on a schedule (weekly, every Sunday at midnight) to perform the following steps:

1.  Checks out the repository.
2.  Sets up the Python environment and installs dependencies.
3.  Runs all the parsers to fetch the latest data from the PokéAPI.
4.  Commits the newly generated data to the `data` branch.

This ensures that the `data` branch always contains the most up-to-date information without any manual intervention.

## License

This project is licensed under the MIT License. See the [LICENSE](https://www.google.com/search?q=LICENSE) file for more details.
