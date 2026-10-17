import pytest

import settings
from layouts import Layout


@pytest.fixture
def files(tmp_path, monkeypatch):
    """Points the plugin at empty rc files in tmp_path; returns a function to fill them."""
    monkeypatch.setattr(settings, "PLUGIN_RC", str(tmp_path / "krunner-layoutfixrc"))
    monkeypatch.setattr(settings, "KXKBRC", str(tmp_path / "kxkbrc"))
    monkeypatch.setattr(settings, "_system_keymap", lambda: {})

    def write(name, text):
        (tmp_path / name).write_text(text)
    return write


def test_reads_plasma_keyboard_settings(files):
    files("kxkbrc", "[Layout]\nLayoutList=us,ru\nVariantList=dvorak,\nModel=pc105\nUse=true\n")
    config = settings.load()
    assert config.layouts == [Layout("us", "dvorak"), Layout("ru")]
    assert config.model == "pc105"
    assert config.extra_languages == []


def test_plugin_settings_override_plasma(files):
    files("kxkbrc", "[Layout]\nLayoutList=us,ru\n")
    files("krunner-layoutfixrc", "[General]\nLayouts=us(colemak), ru\nExtraLanguages=ru, uk\n")
    config = settings.load()
    assert config.layouts == [Layout("us", "colemak"), Layout("ru")]
    assert config.extra_languages == ["ru", "uk"]


def test_falls_back_to_system_keymap_when_plasma_does_not_manage_layouts(files, monkeypatch):
    files("kxkbrc", "[Layout]\nLayoutList=us,de\nUse=false\n")
    monkeypatch.setattr(settings, "_system_keymap", lambda: {"X11Layout": "us,ru", "X11Variant": ","})
    config = settings.load()
    assert config.layouts == [Layout("us"), Layout("ru")]
    assert config.layouts_from == "systemd-localed"


def test_no_settings_at_all(files):
    assert settings.load().layouts == []
