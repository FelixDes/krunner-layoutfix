"""Settings: the keyboard layouts configured in the system and the plugin's optional rc file."""
import configparser
import itertools
import logging
import os
import re
from dataclasses import dataclass

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from layouts import Layout, parse_layouts  # noqa: E402

log = logging.getLogger(__name__)

_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
PLUGIN_RC = os.path.join(_CONFIG_HOME, "krunner-layoutfixrc")  # advanced settings, see README
KXKBRC = os.path.join(_CONFIG_HOME, "kxkbrc")  # Plasma keyboard settings

# Settings are loaded again when one of these files changes.
FILES = (PLUGIN_RC, KXKBRC)


@dataclass
class Settings:
    layouts: list          # [Layout] the user switches between
    model: str             # XKB keyboard model, "" for the default
    layouts_from: str      # where the layouts were found, for the log
    extra_languages: list  # also search app names in these languages, e.g. ["ru"]


def load():
    own = _read_group(PLUGIN_RC, "General")
    extra_languages = re.findall(r"[\w@]+", own.get("extralanguages", ""))

    if own.get("layouts"):
        return Settings(parse_layouts(own["layouts"]), "", PLUGIN_RC, extra_languages)

    plasma = _read_group(KXKBRC, "Layout")
    if plasma.get("layoutlist") and plasma.get("use", "true").lower() != "false":
        layouts = _zip_layouts(plasma["layoutlist"], plasma.get("variantlist", ""))
        return Settings(layouts, plasma.get("model", ""), KXKBRC, extra_languages)

    system = _system_keymap()
    layouts = _zip_layouts(system.get("X11Layout", ""), system.get("X11Variant", ""))
    return Settings(layouts, system.get("X11Model", ""), "systemd-localed", extra_languages)


def _zip_layouts(names, variants):
    """'us,ru' + 'dvorak,' -> [Layout('us', 'dvorak'), Layout('ru')]"""
    pairs = itertools.zip_longest(names.split(","), variants.split(","), fillvalue="")
    return [Layout(name.strip(), variant.strip()) for name, variant in pairs if name.strip()]


def _read_group(path, group):
    """{lowercased key: value} of one [group] of an INI / KDE rc file; {} if there is none."""
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error as error:
        log.warning("cannot read %s: %s", path, error)
        return {}
    return dict(parser[group]) if parser.has_section(group) else {}


def _system_keymap():
    """The system-wide X11 keymap (localectl set-x11-keymap), for when Plasma has no layouts set."""
    try:
        localed = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SYSTEM, Gio.DBusProxyFlags.NONE, None,
            "org.freedesktop.locale1", "/org/freedesktop/locale1", "org.freedesktop.locale1", None)
    except GLib.Error as error:
        log.warning("cannot read the system keymap: %s", error.message)
        return {}
    values = {name: localed.get_cached_property(name) for name in ("X11Layout", "X11Variant", "X11Model")}
    return {name: value.unpack() for name, value in values.items() if value is not None}
