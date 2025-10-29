# PokéDB - Pokémon Data Collector

[![Update Pokémon Data](https://github.com/zhenga8533/pokedb/actions/workflows/update-data.yaml/badge.svg)](https://github.com/zhenga8533/pokedb/actions/workflows/update-data.yaml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python-based tool designed to create a comprehensive and generation-accurate Pokémon database. It intelligently combines data from the official [PokéAPI](https://pokeapi.co/) with historical changes scraped from [Pokémon DB](https://pokemondb.net/) to provide the most precise data for any Pokémon generation.

The parsed generation data is automatically saved to the **`data` branch** weekly, ensuring that you always have access to the latest information.

## Architecture

The project follows modern Python best practices with a clean, modular architecture:

```
pokedb/
├── src/
│   └── pokedb/
│       ├── __init__.py
│       ├── __main__.py      # Entry point
│       ├── api_client.py    # API client with caching
│       ├── scraper.py       # Historical data scraper
│       ├── parsers/         # Resource parsers (ability, item, move, pokemon)
│       └── utils/           # Organized utility modules
│           ├── exceptions.py
│           ├── constants.py
│           ├── file_ops.py
│           ├── config.py
│           ├── api_helpers.py
│           └── text_utils.py
├── pyproject.toml           # Package configuration
├── config.json              # Configuration file
└── requirements.txt         # Dependencies
```

## Documentation

For detailed information about the project's architecture, configuration, data structures, and API usage, please visit the **[Official Wiki](https://github.com/zhenga8533/pokedb/wiki)**.

## Core Features

- **Dual-Source Data Aggregation**: Combines the structured, modern data from PokéAPI with historical data scraped from Pokémon DB.
- **Historical Accuracy**: When parsing older generations, the tool automatically scrapes for and applies historical changes to a Pokémon's types, abilities, stats, EV yields, and more.
- **Concurrent Processing**: Utilizes a thread pool to fetch and process data concurrently.
- **Generation-Specific Data**: Allows you to parse data for a specific Pokémon generation.
- **Automated Data Updates**: Includes a GitHub Actions workflow to automatically update the data on a weekly basis.
- **Structured JSON Output**: Saves the parsed data in a well-structured and easy-to-navigate JSON format.

## Quick Start

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/zhenga8533/pokedb.git
    cd pokedb
    ```

2.  **Install the package:**

    ```bash
    # Install in editable mode with dependencies
    pip install -e .
    ```

    Alternatively, you can install just the dependencies:

    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the collector:**

    ```bash
    # For the latest generation (all parsers)
    python -m pokedb --all

    # For specific parsers only
    python -m pokedb ability move item pokemon

    # For a specific historical generation (e.g., Gen 3)
    python -m pokedb --all --gen 3

    # Disable caching for a fresh parse
    python -m pokedb --all --no-cache
    ```

    For more detailed instructions, see the [**Getting Started**](https://github.com/zhenga8533/pokedb/wiki/Getting-Started) page on the wiki.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
