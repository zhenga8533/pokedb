# PokéAPI Parser

[](https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yaml)
[](https://www.python.org/downloads/release/python-3120/)
[](https://opensource.org/licenses/MIT)

A Python script that fetches data for Pokémon, their forms, abilities, items, and moves from the [PokéAPI](https://pokeapi.co). It processes and deploys the data into a dedicated, versioned `data` branch.

## Features

- **Comprehensive Parsers**: Fetches and processes detailed information for Pokémon, alternate forms (e.g., Mega, G-Max), abilities, items, and moves.
- **Automated Updates**: A GitHub Action runs daily to keep the data current, and can also be triggered manually.
- **Clean Data Branch**: Pushes the structured JSON output to a `data` branch, keeping it separate from the source code.
- **Generation-Specific Data**: Data is organized into folders based on the latest Pokémon generation, and the data within the files is filtered to be relevant to that generation.
- **Caching**: API calls are memoized during a run to prevent redundant fetches of the same URL.
- **Rich Data Output**: Includes evolution chains, generation-specific movesets, item effects, ability flavor text, and more.

---

## Data Output Structure

The generated data is pushed to the `data` branch and organized by the latest generation. The structure is as follows:

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

- **`index.json`**: A top-level index file is created for each generation. It contains metadata about the data generation process and a summary of every item across all categories.

---

## Usage

### Automation via GitHub Actions

The primary method for updating the data is through the built-in GitHub Action.

- **Scheduled**: The action is configured to run automatically once a day.
- **Manual**: You can trigger a run at any time by navigating to the "Actions" tab in the repository, selecting "Update PokéAPI Data", and clicking "Run workflow".

### Local Usage

You can also run the parsers locally.

#### 1\. Setup

- **Prerequisites**: Python 3.12+ and Git.

- **Clone the repository**:

  ```bash
  git clone https://github.com/zhenga8533/pokeapi-parser.git
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

#### 2\. Running the Parsers

Run the parsers from the root directory of the project.

- **Run all parsers**:
  ```bash
  python main.py --all
  ```
- **Run a single parser**:
  ```bash
  python main.py pokemon
  ```
- **Run multiple parsers**:
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
├── .github/workflows/  # GitHub Actions workflow for automation.
├── output/             # (Git-ignored) Default directory for local output.
├── src/pokeapi_parser/
│   ├── parsers/        # Logic for each data type (pokemon, item, etc.).
│   │   ├── base.py     # Abstract base class for all parsers.
│   │   └── ...
│   ├── api_client.py   # Caching client for PokéAPI requests.
│   └── utils.py        # Helper functions.
├── config.json         # Configuration for API URLs and output directories.
├── main.py             # Main entry point.
└── requirements.txt    # Python dependencies.
```

---

## Contributing

Contributions are welcome. Please open an issue or submit a pull request for any improvements or bug fixes.

---

## License

This project is licensed under the MIT License. See the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.
