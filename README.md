# PokéAPI Data Parser

[![GitHub Actions Workflow Status](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml/badge.svg)](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A fully automated, concurrent Python script that fetches comprehensive data for Pokémon, their forms, abilities, items, and moves from the [PokéAPI](https://pokeapi.co). It cleans, processes, and deploys the data into a dedicated, versioned `data` branch in this repository.

## Features

- **Comprehensive Parsers**: Fetches and processes detailed information for Pokémon, all alternate Forms (Mega, G-Max, etc.), Abilities, Items, and Moves.
- **Automated Updates**: A GitHub Action runs on a daily schedule to keep the data fresh, but can also be triggered manually for on-demand updates.
- **Clean Data Branch**: Pushes the structured JSON output to a clean, data-only `data` branch, keeping it separate from the source code.
- **Generation-Specific Data**: All data is automatically organized into folders based on the latest Pokémon generation, and the data within the files is filtered to be relevant to that generation.
- **Intelligent Caching**: All API calls are memoized during a run to ensure that the same URL is never fetched more than once, significantly improving performance.
- **Rich Data Output**: Includes detailed information like evolution chains, generation-specific movesets, item effects, ability flavor text, and much more.

---

## Data Output Structure

The generated data is pushed to the `data` branch and organized by the latest generation found in the PokéAPI. The structure is as follows:

```

└── gen9/
    ├── ability/
    │   └── intimidate.json
    ├── form/
    │   └── charizard-mega-x.json
    ├── item/
    │   └── master-ball.json
    ├── move/
    │   └── flamethrower.json
    ├── pokemon/
    │   └── charizard.json
    └── index.json

```

- **`index.json`**: A top-level index file is created for each generation. It contains metadata about the data generation process and a lightweight summary of every item across all categories (ability, form, item, move, and pokemon) for quick lookups.

---

## Usage

### Automation via GitHub Actions (Recommended)

The primary method for updating the data is through the built-in GitHub Action.

- **On a Schedule**: The action is configured to run automatically once a day.
- **Manually**: You can trigger a run at any time by navigating to the "Actions" tab in this repository, selecting "Update PokéAPI Data", and clicking "Run workflow".

### Local Usage (for Development)

While the project is designed to be automated, you can still run the parsers locally.

#### 1. Setup

- **Prerequisites**: Python 3.12+ and Git must be installed.
- **Clone the repository**:
  ```bash
  git clone [https://github.com/zhenga8533/pokeapi-parser.git](https://github.com/zhenga8533/pokeapi-parser.git)
  cd pokeapi-parser
  ```
- **Create and activate a virtual environment**:

  ```bash
  # For macOS/Linux
  python3 -m venv .venv
  source .venv/bin/activate

  # For Windows
  python -m venv .venv
  .\.venv\Scripts\activate
  ```

- **Install dependencies**:
  ```bash
  pip install -r requirements.txt
  ```

#### 2. Running the Parsers

Run the parsers from the root directory of the project. You can run all parsers or specify one or more to run.

- **Run all parsers (recommended)**:
  ```bash
  python main.py --all
  ```
- **Run a single parser**:
  ```bash
  python main.py pokemon
  ```
- **Run multiple specific parsers**:
  ```bash
  python main.py item move
  ```
- **Specify a Generation**:
  By default, the script will parse data for the latest generation. You can target a specific generation with the `--gen` flag.
  ```bash
  python main.py --all --gen 3
  ```

---

## Project Structure

```

.
├── .github/workflows/ \# Contains the GitHub Actions workflow for automation.
├── output/ \# (Git-ignored) Default directory for local parser output.
├── src/pokeapi_parser/
│   ├── parsers/ \# Contains the logic for each data type (pokemon, item, etc.).
│   │   ├── base.py \# Abstract base class for all parsers.
│   │   └── ...
│   ├── api_client.py \# Centralized, caching client for all PokéAPI requests.
│   └── utils.py \# Helper functions used by the parsers.
├── config.json \# Configuration for API URLs, timeouts, and output directories.
├── main.py \# Main entry point for running the script.
└── requirements.txt \# Python dependencies.

```

---

## Contributing

Contributions are welcome! If you have suggestions for improvements or find a bug, please feel free to open an issue or submit a pull request.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
