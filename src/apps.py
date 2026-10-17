"""Installed applications and System Settings pages, searchable by name."""
import re
import shutil
import unicodedata
from dataclasses import dataclass

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

# Apps come from Gio.AppInfo.get_all() and the DesktopAppInfo class is never
# named here: it moved from Gio to GioUnix, and in older GLib (2.80 in Ubuntu
# 24.04) importing GioUnix breaks the methods of every app object.


@dataclass(frozen=True)
class App:
    id: str            # desktop file id without ".desktop", e.g. "org.kde.dolphin"
    name: str          # shown in the results
    description: str   # generic name or comment, shown under the name
    icon: str
    names: tuple      # _spellings() of the translated, untranslated and extra-language names
    name_words: tuple  # words of the names
    words: tuple       # words of the _spellings() of generic names, keywords and the id


def score(app, text):
    """How well casefolded text matches an app, from 1 (exact name) to 0 (no match)."""
    if text in app.names:
        return 1.0
    if any(name.startswith(text) for name in app.names):
        return 0.9
    if any(word.startswith(text) for word in app.name_words):
        return 0.8
    if any(word.startswith(text) for word in app.words):
        return 0.6
    return 0.0


def fuzzy_score(app, text):
    """Like score(), but allowing typos: a wrong, missing, extra or swapped letter.

    Only names are searched like this, and only for queries of 4 letters and
    more: with a typo allowed, shorter text matches something by chance.
    """
    limit = 0 if len(text) < 4 else 1 if len(text) < 8 else 2
    best = 0.0
    # As without typos, the start of a name beats the start of a word in it.
    for targets, one_typo in ((app.names, 0.5), (app.name_words, 0.45)):
        typos = min((_typos(text, target, limit) for target in targets), default=limit + 1)
        if 0 < typos <= limit:
            best = max(best, one_typo - 0.1 * (typos - 1))
    return best


class AppIndex:
    """Searchable apps, loaded on first use and again after apps are (un)installed."""

    def __init__(self, load=None):
        self._load = load or load_apps
        self._apps = None
        self._extra_languages = []
        # Keep a reference: the monitor only reports changes while it is alive.
        self._monitor = Gio.AppInfoMonitor.get()
        self._monitor.connect("changed", lambda _monitor: self._invalidate())

    def set_extra_languages(self, languages):
        if languages != self._extra_languages:
            self._extra_languages = list(languages)
            self._invalidate()

    def search(self, text):
        """[(score, app)] of the apps matching text, best first.

        Typos are allowed only when nothing matches without them.
        """
        if self._apps is None:
            self._apps = self._load(self._extra_languages)
        text = text.casefold()
        hits = [hit for hit in ((score(app, text), app) for app in self._apps) if hit[0] > 0]
        if not hits:
            hits = [hit for hit in ((fuzzy_score(app, text), app) for app in self._apps) if hit[0] > 0]
        return sorted(hits, key=lambda hit: (-hit[0], hit[1].name.casefold()))

    def _invalidate(self):
        self._apps = None


def load_apps(extra_languages=()):
    return [_app(info, extra_languages) for info in Gio.AppInfo.get_all() if _searchable(info)]


def launch(app_id):
    """Start an app the way Plasma does.

    kstart puts the app into its own systemd scope. Launched directly, it would
    stay in this D-Bus service's cgroup and be killed when the service stops.
    """
    kstart = shutil.which("kstart")
    if kstart:
        Gio.Subprocess.new([kstart, "--application", app_id], Gio.SubprocessFlags.NONE)
    else:  # Plasma 5
        info = next((info for info in Gio.AppInfo.get_all() if info.get_id() == app_id + ".desktop"), None)
        if info:
            info.launch([], None)


def _searchable(info):
    """What the launcher finds: visible apps and System Settings pages (hidden launchers)."""
    if info.get_is_hidden() or not info.get_show_in(None):
        return False
    return not info.get_nodisplay() or info.get_string("X-KDE-AliasFor") == "systemsettings"


def _app(info, extra_languages):
    app_id = (info.get_id() or "").removesuffix(".desktop")
    names = [info.get_name(), info.get_string("Name")]
    terms = [info.get_generic_name(), info.get_locale_string("X-KDE-Keywords"), *info.get_keywords()]
    if extra_languages:
        extra_names, extra_terms = _translations(info.get_filename(), extra_languages)
        names += extra_names
        terms += extra_terms
    terms.append(app_id.rsplit(".", 1)[-1])  # "org.kde.dolphin" -> "dolphin"
    terms = [keyword for term in terms if term for keyword in re.split(r"[,;]", term)]  # keyword lists

    names = _unique(spelling for name in names if name for spelling in _spellings(name))
    icon = info.get_icon()
    return App(
        id=app_id,
        name=info.get_name(),
        description=info.get_generic_name() or info.get_description() or "",
        icon=icon.to_string() if icon else "application-x-executable",
        names=names,
        name_words=_unique(word for name in names for word in name.split()),
        words=_unique(word for term in terms for spelling in _spellings(term) for word in spelling.split()),
    )


def _spellings(text):
    """Casefolded text as it is, without punctuation and without diacritics.

    "Counter-Strike" -> "counter-strike", "counterstrike", "counter strike";
    "Объём" -> "объём", "объем". A query without punctuation or diacritics
    finds a name whatever it has ("dont" finds "Don't Starve"), while
    punctuation and diacritics typed in the query have to match.
    """
    text = unicodedata.normalize("NFC", text.casefold())
    spellings = []
    for form in (text, _drop_marks(text)):
        spellings += [form, _drop_punctuation(form, ""), _drop_punctuation(form, " ")]
    return [spelling for spelling in _unique(spellings) if spelling]


def _drop_marks(text):
    """Removes diacritics: "ё" -> "е", "é" -> "e", "ü" -> "u"."""
    decomposed = unicodedata.normalize("NFD", text)
    return unicodedata.normalize("NFC", "".join(char for char in decomposed if unicodedata.category(char) != "Mn"))


def _drop_punctuation(text, replacement):
    """Replaces punctuation and symbols (Unicode categories P* and S*) and squeezes the spaces."""
    return " ".join("".join(replacement if unicodedata.category(char)[0] in "PS" else char for char in text).split())


def _translations(path, languages):
    """Names and search terms of a desktop file in other languages.

    Gio keeps only the current language, so the file is read again with all translations.
    """
    keyfile = GLib.KeyFile()
    try:
        keyfile.load_from_file(path, GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    except GLib.Error:
        return [], []

    def get(key, lang):
        try:
            return keyfile.get_locale_string("Desktop Entry", key, lang)
        except GLib.Error:
            return None

    names = [get("Name", lang) for lang in languages]
    terms = [get(key, lang) for lang in languages for key in ("GenericName", "Keywords", "X-KDE-Keywords")]
    return names, terms


def _typos(text, target, limit):
    """Fewest typos that turn text into the beginning of target, or limit + 1 if more.

    The Damerau-Levenshtein distance from text to the closest prefix of target.
    """
    target = target[:len(text) + limit]
    if len(target) < len(text) - limit:
        return limit + 1
    earlier, before = None, list(range(len(target) + 1))  # rows i - 2 and i - 1
    for i in range(1, len(text) + 1):
        row = [i] + [0] * len(target)
        for j in range(1, len(target) + 1):
            row[j] = min(
                before[j] + 1,                                   # extra letter
                row[j - 1] + 1,                                  # missing letter
                before[j - 1] + (text[i - 1] != target[j - 1]),  # wrong letter
            )
            if i > 1 and j > 1 and text[i - 1] == target[j - 2] and text[i - 2] == target[j - 1]:
                row[j] = min(row[j], earlier[j - 2] + 1)         # swapped letters
        if min(row) > limit:
            return limit + 1
        earlier, before = before, row
    return min(before)


def _unique(items):
    return tuple(dict.fromkeys(items))
