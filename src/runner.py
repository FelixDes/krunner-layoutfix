#!/usr/bin/env python3
"""KRunner plugin: finds applications typed in the wrong keyboard layout.

This is a D-Bus runner (org.kde.krunner1): KRunner and the Application
Launcher send it every query and show the matches it returns.
"""
import argparse
import logging
import os
from dataclasses import dataclass

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

import apps  # noqa: E402
import settings  # noqa: E402
from layouts import Converter, load_keymaps  # noqa: E402

log = logging.getLogger("krunner-layoutfix")

BUS_NAME = "io.github.felixdes.KRunnerLayoutFix"
OBJECT_PATH = "/runner"
MIN_LENGTH = 2
MAX_RESULTS = 8

INTERFACE = """
<node>
  <interface name="org.kde.krunner1">
    <method name="Actions">
      <arg name="actions" type="a(sss)" direction="out"/>
    </method>
    <method name="Match">
      <arg name="query" type="s" direction="in"/>
      <arg name="matches" type="a(sssida{sv})" direction="out"/>
    </method>
    <method name="Run">
      <arg name="matchId" type="s" direction="in"/>
      <arg name="actionId" type="s" direction="in"/>
    </method>
    <method name="Teardown"/>
  </interface>
</node>
"""

# KRunner::QueryMatch::CategoryRelevance
HIGHEST, LOW = 100, 30


@dataclass
class Match:
    app: apps.App
    score: float
    query: str    # as typed
    variant: str  # re-typed in the layout that finds the app


class LayoutFix:
    """The plugin itself, without the D-Bus part."""

    def __init__(self, index, converter=None):
        self.index = index
        self.converter = converter or Converter([])
        self._settings_stamp = None

    def reload_settings_if_changed(self):
        stamp = [_mtime(path) for path in settings.FILES]
        if stamp == self._settings_stamp:
            return
        self._settings_stamp = stamp
        config = settings.load()
        log.info("layouts from %s: %s", config.layouts_from, ", ".join(map(str, config.layouts)) or "none")
        keymaps = load_keymaps(config.layouts, config.model)
        if len(keymaps) < 2:
            log.warning("need at least two keyboard layouts to convert between")
        self.converter = Converter(keymaps)
        self.index.set_extra_languages(config.extra_languages)

    def match(self, query):
        query = query.strip()
        if len(query) < MIN_LENGTH:
            return []
        variants = self.converter.retype(query)
        if not variants:
            return []
        # A query that finds something as typed was probably typed in the right
        # layout: then only apps that a variant finds even better are shown.
        as_typed = self.index.search(query)
        bar = as_typed[0][0] if as_typed else 0.0
        best = {}
        for variant in variants:
            for score, app in self.index.search(variant):
                current = best.get(app.id)
                if score > bar and (current is None or score > current.score):
                    best[app.id] = Match(app, score, query, variant)
        ranked = sorted(best.values(), key=lambda match: (-match.score, match.app.name.casefold()))
        return ranked[:MAX_RESULTS]


def serve(plugin):
    interface = Gio.DBusNodeInfo.new_for_xml(INTERFACE).interfaces[0]
    loop = GLib.MainLoop()

    def on_method_call(_connection, _sender, _path, _interface, method, args, invocation):
        try:
            if method == "Match":
                plugin.reload_settings_if_changed()
                matches = [_to_dbus(match) for match in plugin.match(*args.unpack())]
                invocation.return_value(GLib.Variant("(a(sssida{sv}))", (matches,)))
            elif method == "Run":
                match_id, _action_id = args.unpack()
                apps.launch(match_id)
                invocation.return_value(None)
            elif method == "Actions":
                invocation.return_value(GLib.Variant("(a(sss))", ([],)))
            else:  # Teardown: the search session is over, nothing to clean up
                invocation.return_value(None)
        except Exception as error:
            log.exception("%s failed", method)
            invocation.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(error))

    def on_bus_acquired(connection, _name):
        connection.register_object(OBJECT_PATH, interface, on_method_call)

    def on_name_lost(_connection, _name):
        log.error("cannot own %s on the session bus, is another instance running?", BUS_NAME)
        loop.quit()

    Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.NONE, on_bus_acquired, None, on_name_lost)
    loop.run()


def _to_dbus(match):
    return (
        match.app.id,
        match.app.name,
        match.app.icon,
        HIGHEST if match.score >= 0.9 else LOW,
        match.score,
        {"subtext": GLib.Variant("s", _subtext(match))},
    )


def _subtext(match):
    """Why the app is shown and what it is: "ыеуфь → steam · Game launcher"."""
    retyped = f"{match.query} → {match.variant}"
    return f"{retyped} · {match.app.description}" if match.app.description else retyped


def _mtime(path):
    try:
        return os.stat(path).st_mtime_ns
    except FileNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser(description="KRunner plugin: finds applications typed in the wrong keyboard layout.")
    parser.add_argument("--query", metavar="TEXT", help="print what a search for TEXT finds, without D-Bus, and exit")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    plugin = LayoutFix(apps.AppIndex())
    plugin.reload_settings_if_changed()
    if args.query is None:
        serve(plugin)
        return

    print("re-typed:", ", ".join(plugin.converter.retype(args.query.strip())) or "-")
    matches = plugin.match(args.query)
    for match in matches:
        print(f"{match.score:.2f}  {match.app.name}  ({match.app.id})  {_subtext(match)}")
    if not matches:
        print("no matches")


if __name__ == "__main__":
    main()
