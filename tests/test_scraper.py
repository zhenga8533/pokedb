from bs4 import BeautifulSoup

from pokedb.scraper import (
    _parse_ability,
    _parse_simple_stat,
    _parse_special_stat,
    _parse_types,
    scrape_pokemon_changes,
)
from pokedb.config import load_config


def _list_item(html):
    return BeautifulSoup(html, "html.parser").find("li")


def test_ability_history_uses_canonical_link_slug():
    item = _list_item(
        '<li>Gengar has the <a href="/ability/levitate">Levitate</a> ability.</li>'
    )

    assert _parse_ability(item, item.get_text()) == {"ability": "levitate"}


def test_form_qualifier_is_preserved_for_simple_changes():
    item = _list_item(
        "<li>Rotom (Heat Rotom) has a base Friendship value of 70.</li>"
    )

    assert _parse_simple_stat("base_happiness")(item, item.get_text()) == {
        "base_happiness": 70,
        "form": "Heat Rotom",
    }


def test_form_qualifier_is_preserved_for_type_changes():
    item = _list_item(
        '<li>Rotom (Wash Rotom) is <a class="itype">Electric</a> /'
        '<a class="itype">Ghost</a> type.</li>'
    )

    assert _parse_types(item, item.get_text()) == {
        "types": ["electric", "ghost"],
        "form": "Wash Rotom",
    }


def test_generation_one_special_remains_one_stat():
    item = _list_item("<li>Pikachu has a base Special stat of 50.</li>")

    assert _parse_special_stat(item, item.get_text()) == {
        "stats": {"special": 50}
    }


def test_scraper_reports_changes_it_cannot_scope(monkeypatch):
    html = b"""
        <h2>Pikachu changes</h2>
        <ul>
          <li><abbr>Generation 1</abbr>, Pikachu has a base Special stat of 50.</li>
          <li>In Pokemon Yellow, Pikachu has a base Friendship value of 90.</li>
        </ul>
    """

    class Response:
        content = html

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr("pokedb.scraper.requests.get", lambda *args, **kwargs: Response())

    result = scrape_pokemon_changes("pikachu", load_config().without_cache())

    assert result["changes"][0]["change"] == {"stats": {"special": 50}}
    assert result["unsupported_changes"] == [
        "In Pokemon Yellow, Pikachu has a base Friendship value of 90."
    ]
