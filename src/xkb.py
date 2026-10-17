"""Minimal libxkbcommon binding: which character every key types in a layout.

libxkbcommon is installed on every Plasma system (KWin and Qt use it), so
reading layouts through it needs no extra dependency and understands every
layout and variant the system has, including custom ones in ~/.config/xkb.
"""
import ctypes
import re

_lib = ctypes.CDLL("libxkbcommon.so.0")
_u32 = ctypes.c_uint32
_ptr = ctypes.c_void_p


class _RuleNames(ctypes.Structure):
    _fields_ = [(field, ctypes.c_char_p) for field in ("rules", "model", "layout", "variant", "options")]


def _bind(name, restype, *argtypes):
    func = getattr(_lib, name)
    func.restype = restype
    func.argtypes = argtypes
    return func


_context_new = _bind("xkb_context_new", _ptr, ctypes.c_int)
_keymap_new_from_names = _bind("xkb_keymap_new_from_names", _ptr, _ptr, ctypes.POINTER(_RuleNames), ctypes.c_int)
_keymap_unref = _bind("xkb_keymap_unref", None, _ptr)
_min_keycode = _bind("xkb_keymap_min_keycode", _u32, _ptr)
_max_keycode = _bind("xkb_keymap_max_keycode", _u32, _ptr)
_key_get_name = _bind("xkb_keymap_key_get_name", ctypes.c_char_p, _ptr, _u32)
_num_levels_for_key = _bind("xkb_keymap_num_levels_for_key", _u32, _ptr, _u32, _u32)
_key_get_syms_by_level = _bind(
    "xkb_keymap_key_get_syms_by_level", ctypes.c_int, _ptr, _u32, _u32, _u32, ctypes.POINTER(ctypes.POINTER(_u32)))
_keysym_to_utf32 = _bind("xkb_keysym_to_utf32", _u32, _u32)

# Ignore XKB_DEFAULT_* variables: the caller says exactly which layout it wants.
_XKB_CONTEXT_NO_ENVIRONMENT_NAMES = 1 << 1
_context = _context_new(_XKB_CONTEXT_NO_ENVIRONMENT_NAMES)

# The typing block: TLDE, AE01.., AD01.., AC01.., AB01.., BKSL, LSGT.
# The keypad repeats digits and "." and would only make the mapping ambiguous.
TYPING_KEYS = re.compile(r"TLDE|BKSL|LSGT|A[EDCB]\d\d")

# Plain and Shift. AltGr levels differ too much between layouts to be useful.
LEVELS = 2


def key_chars(layout, variant="", model=""):
    """Characters a layout types, keyed by (key name, level).

    key_chars("ru")[("AC02", 0)] == "ы", key_chars("ru")[("AC02", 1)] == "Ы"
    Raises ValueError if the layout or variant does not exist.
    """
    names = _RuleNames(None, model.encode() or None, layout.encode(), variant.encode() or None, None)
    keymap = _keymap_new_from_names(_context, ctypes.byref(names), 0)
    if not keymap:
        raise ValueError(f"unknown keyboard layout {layout}" + (f"({variant})" if variant else ""))
    try:
        chars = {}
        for key in range(_min_keycode(keymap), _max_keycode(keymap) + 1):
            name = (_key_get_name(keymap, key) or b"").decode()
            if not TYPING_KEYS.fullmatch(name):
                continue
            for level in range(min(LEVELS, _num_levels_for_key(keymap, key, 0))):
                syms = ctypes.POINTER(_u32)()
                if _key_get_syms_by_level(keymap, key, 0, level, ctypes.byref(syms)) != 1:
                    continue
                codepoint = _keysym_to_utf32(syms[0])
                if codepoint:  # 0 for keys that type nothing, e.g. dead keys
                    chars[(name, level)] = chr(codepoint)
        return chars
    finally:
        _keymap_unref(keymap)
