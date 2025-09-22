# PokéAPI Parser

[](https://www.google.com/search?q=https://github.com/zhenga8533/pokeapi-parser/actions/workflows/update-data.yml)
[](https://www.python.org/downloads/release/python-3120/)
[](https://opensource.org/licenses/MIT)

A fully automated tool that parses comprehensive data from the [PokéAPI](https://pokeapi.co), cleans it, and deploys it to a dedicated `data` branch in this repository.

## Features

- **Comprehensive Parsers**: Fetches and processes detailed information for Abilities, Items, Moves, and Pokémon.
- **Automated Updates**: A GitHub Action runs on a daily schedule to keep the data fresh, or can be triggered manually.
- **Clean Data Branch**: Pushes the output to a clean, data-only `data` branch, separate from the source code.
- **Versioned by Generation**: All data is automatically organized into folders based on the latest Pokémon generation.
- **Convenient Summaries**: Each data category includes a `summary.json` file, providing a lightweight index of all items for easy lookups.

---

## Data Output Structure

The data is organized on the `data` branch in the following structure. The `genX` folder will always correspond to the latest generation found in the PokéAPI.

```
└── gen9/
    ├── ability/
    │   ├── summary.json
    │   ├── stench.json
    │   └── ...
    ├── item/
    │   ├── summary.json
    │   ├── master-ball.json
    │   └── ...
    ├── move/
    │   ├── summary.json
    │   ├── pound.json
    │   └── ...
    └── pokemon/
        ├── summary.json
        ├── pikachu.json
        └── ...
```

---

## Automation via GitHub Actions

The primary method for updating the data is through the built-in GitHub Action.

- **On a Schedule**: The action is configured to run automatically once a day.
- **Manually**: You can trigger a run at any time by navigating to the "Actions" tab in this repository, selecting "Update PokéAPI Data", and clicking "Run workflow".

---

## Local Usage (for Development)

While the project is designed to be automated, you can still run the parsers locally.

### 1\. Setup

- **Prerequisites**: Python 3.12+ and Git must be installed.
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

### 2\. Running the Parsers

Run the parsers from the root directory of the project.

- **Run a single parser**:
  ```bash
  python main.py ability
  ```
- **Run multiple specific parsers**:
  ```bash
  python main.py item move
  ```
- **Run all parsers**:
  ```bash
  python main.py --all
  ```

---

## License

This project is licensed under the MIT License.
