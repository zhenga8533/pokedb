# Pokémon Data Collector

[![Update Pokémon Data](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml/badge.svg)](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python-based tool designed to create a comprehensive and generation-accurate Pokémon database. It intelligently combines data from the official [PokéAPI](httpshttps://pokeapi.co/) with historical changes scraped from [Pokémon DB](https://pokemondb.net/) to provide the most precise data for any Pokémon generation.

The parsed generation data is automatically saved to the **`data` branch** weekly, ensuring that you always have access to the latest information.

## Documentation

For detailed information about the project's architecture, configuration, and data structures, please visit the **[Official Wiki](https://github.com/zhenga8533/pokeapi-parser/wiki)**.

## Features

- **Dual-Source Data Aggregation**: Combines the structured, modern data from PokéAPI with historical data scraped from Pokémon DB.
- **Historical Accuracy**: When parsing older generations, the tool automatically scrapes for and applies historical changes to a Pokémon's types, abilities, stats, EV yields, and more.
- **Comprehensive Data Parsing**: Extracts data for Pokémon (including all forms and varieties), abilities, items, and moves.
- **Concurrent Processing**: Utilizes a thread pool to fetch and process data concurrently, significantly speeding up the collection process.
- **Configuration-driven**: Easily configure settings like API endpoints, timeouts, and output directories through a simple `config.json` file.
- **Structured JSON Output**: Saves the parsed data in a well-structured and easy-to-navigate JSON format, tailored to be accurate for the specified generation.
- **Automated Data Updates**: Includes a GitHub Actions workflow to automatically update the data on a weekly basis.

## How to Use

### Prerequisites

- Python 3.12 or higher

### Installation

1.  Clone the repository:

    ```bash
    git clone [https://github.com/zhenga8533/pokeapi-parser.git](https://github.com/zhenga8533/pokeapi-parser.git)
    cd pokeapi-parser
    ```

2.  Install the required dependencies:

    ```bash
    pip install -r requirements.txt
    ```

### Running the Collector

You can run all collectors at once or specify the ones you need.

- **Run all collectors for the latest generation**:

  ```bash
  python main.py --all
  ```

- **Run specific collectors**:
  You can specify one or more collectors to run by listing their names. The available options are `pokemon`, `ability`, `item`, and `move`.

  ```bash
  python main.py pokemon item
  ```

- **Parse data for a specific (historical) generation**:
  Use the `--gen` flag to parse all data for a specific generation. If the requested generation is not the latest one, the tool will automatically scrape Pokémon DB for any historical changes to ensure the data is accurate for that time period. The output will be placed in a folder corresponding to that generation (e.g., `output/gen3`).

  ```bash
  python main.py --all --gen 3
  ```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
