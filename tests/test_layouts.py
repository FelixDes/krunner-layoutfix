import pytest

from layouts import Converter, Layout, load_keymaps, parse_layouts


def retype(text, layouts):
    return Converter(load_keymaps(parse_layouts(layouts))).retype(text)


@pytest.mark.parametrize("typed, layouts, meant", [
    ("ыеуфь", "us,ru", "steam"),
    ("ghbdtn", "us,ru", "привет"),
    ("ЫЕУФЬ", "us,ru", "STEAM"),             # Shift or Caps Lock
    ("ыеeam", "us,ru", "steam"),             # layout switched halfway
    ("№1", "us,ru", "#1"),                   # Shift on the digit row
    ("жлвфь", "us(dvorak),ru", "steam"),     # Dvorak user, Russian layout active
    ("iudukybdo", "us(dvorak),ru", "параметры"),
    ("іфыр", "us,by", "bash"),
    ("zakuake", "us,de", "yakuake"),         # QWERTZ
    ("דאקשצ", "us,il", "steam"),
])
def test_retypes_into_the_meant_layout(typed, layouts, meant):
    assert meant in retype(typed, layouts)


def test_tries_every_pair_of_layouts():
    assert "kate" in retype("vakd", "us,us(dvorak)")  # QWERTY active, Dvorak meant
    assert "vakd" in retype("kate", "us,us(dvorak)")  # and the other way round


def test_skips_pairs_that_cannot_have_typed_the_text():
    # "и" is not in the Belarusian layout, so by -> us is not tried ("иash")
    assert retype("ифыр", "us,ru,by") == ["bash", "іфыр"]


@pytest.mark.parametrize("typed, layouts", [
    ("steam", "us"),             # a single layout
    ("123", "us,ru"),            # the same in both layouts
    ("ыеуфь", "us,us(dvorak)"),  # cannot be typed in either
])
def test_no_variants(typed, layouts):
    assert retype(typed, layouts) == []


def test_parse_layouts():
    assert parse_layouts("us(dvorak), ru") == [Layout("us", "dvorak"), Layout("ru")]
    assert parse_layouts("") == []


def test_unknown_layouts_are_skipped():
    assert len(load_keymaps(parse_layouts("us, nosuchlayout, ru(nosuchvariant), ru"))) == 2
