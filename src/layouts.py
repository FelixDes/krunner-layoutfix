"""Re-typing text as if it had been typed with another keyboard layout active."""
import itertools
import logging
import re
from dataclasses import dataclass

import xkb

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Layout:
    name: str          # XKB layout, e.g. "us"
    variant: str = ""  # XKB variant, e.g. "dvorak"

    def __str__(self):
        return f"{self.name}({self.variant})" if self.variant else self.name


def parse_layouts(text):
    """'us(dvorak), ru' -> [Layout('us', 'dvorak'), Layout('ru')]"""
    return [Layout(name, variant) for name, variant in re.findall(r"([\w-]+)(?:\(([\w-]+)\))?", text)]


def load_keymaps(layouts, model=""):
    """xkb.key_chars() of every layout that exists; unknown ones are logged and skipped."""
    keymaps = []
    for layout in dict.fromkeys(layouts):  # drop duplicates, keep order
        try:
            keymaps.append(xkb.key_chars(layout.name, layout.variant, model))
        except ValueError as error:
            log.warning("%s", error)
    return keymaps


class Converter:
    """Maps text typed in one layout to what the same keys type in another.

    A character is looked up as (key, level) in the layout it was typed in and
    replaced with the character on the same key and level of the other layout:
    "ы" is AC02 in ru, AC02 is "s" in us, so ru -> us turns "ыеуфь" into "steam".
    Every ordered pair of layouts is tried, so any number of layouts works.
    """

    def __init__(self, keymaps):
        """keymaps: list of xkb.key_chars() results, one per layout."""
        self._pairs = []
        for typed_in, meant in itertools.permutations(keymaps, 2):
            typeable = set(typed_in.values()) | set(meant.values())
            self._pairs.append((_translation(typed_in, meant), typeable))

    def retype(self, text):
        """Every different text the same keystrokes give in another layout.

        A pair of layouts is skipped when it cannot have produced the text.
        Characters the typed-in layout does not have are kept as they are, so
        a query where the layout was switched halfway ("ыеeam") becomes "steam".
        """
        variants = []
        for table, typeable in self._pairs:
            if all(char in typeable or char.isspace() for char in text):
                variant = text.translate(table)
                if variant != text and variant not in variants:
                    variants.append(variant)
        return variants


def _translation(typed_in, meant):
    """str.translate() table: character in one layout -> character on the same key in another."""
    position = {}
    # When a character is on several keys, prefer the unshifted one, and avoid
    # LSGT: it exists only on ISO keyboards ("<" is also Shift+"," in us).
    for key, char in sorted(typed_in.items(), key=lambda item: (item[0][0] == "LSGT", item[0][1])):
        position.setdefault(char, key)
    return {ord(char): meant[key] for char, key in position.items() if key in meant and meant[key] != char}
