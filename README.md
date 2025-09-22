# PokéAPI Parser

[![Update PokéAPI Data](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml/badge.svg)](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python-based tool designed to fetch, parse, and structure data from the [PokéAPI](https://pokeapi.co/). This project automates the process of collecting detailed information about Pokémon, their abilities, moves, items, and more, and saves it into a clean, easy-to-use JSON format.

The parsed generation data is automatically saved to the **`data` branch** weekly, ensuring that you always have the latest information.

## Documentation

For detailed information about the project's architecture, configuration, and data structures, please visit the **[Official Wiki](https://github.com/zhenga8533/pokeapi-parser/wiki)**.

## Features

- **Comprehensive Data Parsing**: Extracts data for Pokémon (including all forms and varieties), abilities, items, and moves.
- **Concurrent Processing**: Utilizes a thread pool to fetch data from the API concurrently, significantly speeding up the parsing process.
- **Configuration-driven**: Easily configure settings like API endpoints, timeouts, and output directories through the `config.json` file.
- **Generation-specific Data**: Allows you to parse data up to a specific Pokémon generation.
- **Automated Data Updates**: Includes a GitHub Actions workflow to automatically update the data on a weekly basis.
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

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
