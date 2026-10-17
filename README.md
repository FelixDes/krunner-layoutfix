<p align="center"><img src="data/logo.svg" width="128" alt=""></p>

<h1 align="center">krunner-layoutfix</h1>

A KRunner plugin that finds applications when you typed their name with the
wrong keyboard layout active. Works in KRunner (Alt+Space) and in the search of
the Application Launcher.

| You typed   | Layouts                               | You get               |
|-------------|---------------------------------------|-----------------------|
| `ыеуфь`     | English + Russian                     | Steam                 |
| `вшызд`     | English + Russian                     | Display Configuration |
| `gfhfvtnhs` | English + Russian, Russian interface  | Параметры системы     |
| `жлвфь`     | Dvorak + Russian                      | Steam                 |
| `vakd`      | QWERTY + Dvorak                       | Kate                  |

## How it works

The plugin takes the keyboard layouts you switch between from Plasma's keyboard
settings. For every pair of them it looks up which key typed each character in
one layout and takes what the same key types in the other one. The key maps come
from the system's XKB data, so any layout and variant works: Dvorak, Colemak,
QWERTZ, Belarusian, Hebrew, your own layouts in `~/.config/xkb`.

The re-typed text is searched in application names, generic names and keywords,
and in System Settings pages, the same places the launcher searches. Results
show up only when the query as typed finds nothing better, so queries typed in
the right layout get no extra noise.

Punctuation and diacritics in names are optional: `dont` finds Don't Starve
Together, `counterstrike` and `counter strike` find Counter-Strike, `объем`
finds Объём. Punctuation and diacritics you do type have to match.

Typos are forgiven when nothing matches without them: one wrong, missing,
extra or swapped letter in queries of 4 letters and more, two from 8 letters.

## Install

Needs Plasma 6 (Plasma 5 should work too) and PyGObject:

```sh
sudo pacman -S python-gobject     # Arch
sudo apt install python3-gi       # Debian, Ubuntu
sudo dnf install python3-gobject  # Fedora
```

Then:

```sh
git clone https://github.com/FelixDes/krunner-layoutfix
cd krunner-layoutfix
./install.sh
```

It installs into `~/.local/share` and needs no root. Run it again to update,
`./uninstall.sh` to remove. The plugin can be turned off in System Settings →
Search → Plasma Search → Wrong Keyboard Layout.

## Advanced settings

Usually nothing needs to be configured. For the cases below, create
`~/.config/krunner-layoutfixrc`. Changes apply on the next search.

```ini
[General]
# Layouts to convert between, in XKB names as setxkbmap takes them. By default
# they come from Plasma's keyboard settings, falling back to the system keymap
# (localectl). Set this if your layouts are managed elsewhere, e.g. by fcitx5.
Layouts=us(dvorak),ru

# Also search application names in these languages, as in .desktop files
# (ru, uk, pt_BR). By default only the interface language is searched, like
# KRunner itself does. Useful with an English interface and Russian app names.
ExtraLanguages=ru
```

The same from the command line:

```sh
kwriteconfig6 --file krunner-layoutfixrc --group General --key ExtraLanguages ru
```

## Troubleshooting

See what the plugin does with a query, without KRunner:

```console
$ python3 ~/.local/share/krunner-layoutfix/runner.py --query ыеуфь
INFO: layouts from /home/you/.config/kxkbrc: us, ru
re-typed: steam
1.00  Steam  (steam)  ыеуфь → steam · Application for managing and playing games on Steam
```

It shows which layouts are used and where they came from, how the query was
re-typed and what was found. Please include this output in bug reports.

## Development

```
src/
  runner.py    D-Bus interface for KRunner, entry point
  layouts.py   re-typing text in another layout
  xkb.py       key maps from libxkbcommon
  apps.py      applications and System Settings pages, search
  settings.py  configured layouts and advanced settings
```

Try a change without installing it: `python3 src/runner.py --query ыеуфь`.
Tests use the system's XKB data and need pytest:

```sh
python3 -m pytest
```

## License

MIT
