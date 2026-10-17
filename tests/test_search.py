import gi
import pytest

gi.require_version("Gio", "2.0")
from gi.repository import Gio  # noqa: E402

import apps  # noqa: E402
import runner  # noqa: E402
from layouts import Converter, load_keymaps, parse_layouts  # noqa: E402
from runner import LayoutFix  # noqa: E402


@pytest.fixture
def entry(tmp_path):
    """Writes a desktop file with the given keys and returns its DesktopAppInfo."""
    def create(**keys):
        path = tmp_path / f"app{len(list(tmp_path.iterdir()))}.desktop"
        lines = ["[Desktop Entry]", "Type=Application", "Exec=true", *(f"{k}={v}" for k, v in keys.items())]
        path.write_text("\n".join(lines) + "\n")
        return Gio.DesktopAppInfo.new_from_filename(str(path))
    return create


@pytest.fixture
def app(entry):
    return lambda name, **keys: apps._app(entry(Name=name, **keys), [])


def plugin(*app_list, layouts="us,ru"):
    index = apps.AppIndex(load=lambda _languages: list(app_list))
    return LayoutFix(index, Converter(load_keymaps(parse_layouts(layouts))))


def found(plugin, query):
    return [(match.app.name, match.variant) for match in plugin.match(query)]


def test_score_prefers_whole_names_then_prefixes_then_keywords(app):
    steam = app("Steam", Keywords="game;valve;")
    assert apps.score(steam, "steam") == 1.0
    assert apps.score(steam, "ste") == 0.9
    assert apps.score(app("System Settings"), "sett") == 0.8  # a word of the name
    assert apps.score(steam, "val") == 0.6                    # a keyword
    assert apps.score(steam, "eam") == 0.0                    # no infix matches: too noisy for gibberish


def test_punctuation_in_names_is_optional(app):
    starve = app("Don't Starve Together")
    assert apps.score(starve, "dont") == 0.9
    assert apps.score(starve, "don't") == 0.9
    assert apps.score(starve, "dont starve together") == 1.0
    strike = app("Counter-Strike 2")
    assert apps.score(strike, "counterstrike") == 0.9
    assert apps.score(strike, "counter strike") == 0.9
    assert apps.score(strike, "strike") == 0.8


def test_punctuation_in_the_query_has_to_match(app):
    assert apps.score(app("Counter-Strike 2"), "counter_strike") == 0.0


def test_keywords_without_punctuation(app):
    network = app("Network", Keywords="wi-fi;internet;")
    assert apps.score(network, "wifi") == 0.6
    assert apps.score(network, "wifiinternet") == 0.0  # neighbouring keywords are not glued


def test_diacritics_in_names_are_optional(app):
    assert apps.score(app("Paramètres système"), "parametres") == 0.9
    assert apps.score(app("Объём диска"), "объем") == 0.9
    assert apps.score(app("Paramètres système"), "paramè") == 0.9
    assert apps.score(app("Cafe"), "café") == 0.0  # diacritics typed in the query have to match


def test_description_is_the_generic_name_or_the_comment(app):
    assert app("Steam", GenericName="Game launcher", Comment="Play games").description == "Game launcher"
    assert app("Display", Comment="Monitors and screens").description == "Monitors and screens"
    assert app("Tool").description == ""


def test_subtext_shows_how_the_query_was_retyped_and_what_the_app_is(app):
    [match] = plugin(app("Steam", GenericName="Game launcher")).match("ыеуфь")
    assert runner._subtext(match) == "ыеуфь → steam · Game launcher"
    [match] = plugin(app("Steam")).match("ыеуфь")
    assert runner._subtext(match) == "ыеуфь → steam"


def test_typos(app):
    steam = app("Steam")
    assert apps.fuzzy_score(steam, "stean") == 0.5  # wrong letter
    assert apps.fuzzy_score(steam, "stam") == 0.5   # missing letter
    assert apps.fuzzy_score(steam, "steeam") == 0.5  # extra letter
    assert apps.fuzzy_score(steam, "stema") == 0.5  # swapped letters
    assert apps.fuzzy_score(steam, "stm") == 0.0    # too short to guess
    settings = app("System Settings")
    assert apps.fuzzy_score(settings, "sustem setyings") == 0.4  # two typos in a long query
    assert apps.fuzzy_score(settings, "sustwm") == 0.0           # but only one in a short one


def test_typos_are_allowed_only_when_nothing_matches_without_them(app):
    steam, deck = app("Steam"), app("Stream Deck")
    index = apps.AppIndex(load=lambda _languages: [steam, deck])
    assert [hit[1].name for hit in index.search("steam")] == ["Steam"]
    assert [hit[1].name for hit in index.search("strem")] == ["Stream Deck"]


def test_finds_apps_typed_in_the_wrong_layout_with_a_typo(app):
    assert found(plugin(app("Steam")), "ыеуфт") == [("Steam", "stean")]


def test_finds_names_with_punctuation_typed_in_the_wrong_layout(app):
    assert found(plugin(app("Don't Starve Together")), "вщте") == [("Don't Starve Together", "dont")]


def test_finds_apps_typed_in_the_wrong_layout(app):
    found_in = plugin(app("Steam"), app("System Settings"))
    assert found(found_in, "ыеуфь") == [("Steam", "steam")]
    assert found(found_in, "ыуеештпы") == [("System Settings", "settings")]


def test_ignores_queries_that_already_find_something_as_typed(app):
    games, bush = app("Игры"), app("Bush")  # "bu" on the Russian layout is "иг"
    assert found(plugin(games, bush), "bu") == []
    assert found(plugin(games, bush), "иг") == []
    assert found(plugin(games), "bu") == [("Игры", "иг")]


def test_short_queries_are_ignored(app):
    assert found(plugin(app("Steam")), "ы") == []


def test_extra_languages(entry):
    settings = entry(Name="System Settings", **{"Name[ru]": "Параметры системы"})
    assert "параметры системы" not in apps._app(settings, []).names
    assert "параметры системы" in apps._app(settings, ["ru"]).names


def test_system_settings_pages_are_searchable_other_hidden_entries_are_not(entry):
    assert apps._searchable(entry(Name="Display", NoDisplay="true", **{"X-KDE-AliasFor": "systemsettings"}))
    assert not apps._searchable(entry(Name="PDF", NoDisplay="true", **{"X-KDE-AliasFor": "okular"}))
    assert not apps._searchable(entry(Name="Helper", NoDisplay="true"))
    assert apps._searchable(entry(Name="Steam"))
