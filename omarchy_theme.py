"""Shared helpers for reading the active omarchy theme's colors.

Every device driver in this repo syncs its RGB to the current omarchy theme, so
the colour parsing, saturation boosting and palette building live here instead
of being copy-pasted into each `set_rgb.py`.

omarchy 4 moved the active theme's `colors.toml` from `~/.config/...` to
`~/.local/state/...`; `load_theme_colors()` tries the new path first and falls
back to the old one, so the same code works on omarchy 3 and 4.
"""

import colorsys
import os

# Active-theme colour file. New omarchy 4 location first, legacy location second.
COLORS_PATHS = (
    "~/.local/state/omarchy/current/theme/colors.toml",
    "~/.config/omarchy/current/theme/colors.toml",
)

# Terminal palette keys used (with `accent`) to build a multi-colour animation.
PALETTE_KEYS = (
    "accent", "color1", "color2", "color3", "color4", "color5", "color6",
    "color9", "color10", "color11", "color12", "color13", "color14",
)


def parse_hex(hex_str):
    """Parse a `#rrggbb` (or `rrggbb`) string to an (r, g, b) tuple, or None."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        return None
    try:
        return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
    except ValueError:
        return None


def saturate(r, g, b, min_saturation=1.0, min_value=0.85):
    """Boost saturation and brightness of an RGB colour for vivid LED output."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    s = max(s, min_saturation)
    v = max(v, min_value)
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return (int(r2 * 255), int(g2 * 255), int(b2 * 255))


def find_colors_path():
    """Return the first existing theme colors.toml path, or None."""
    for path in map(os.path.expanduser, COLORS_PATHS):
        if os.path.exists(path):
            return path
    return None


def load_theme_colors():
    """Parse the active theme's colors.toml into {key: (r, g, b)}.

    Returns an empty dict if no theme file is found. Only `key = "#rrggbb"`
    lines are kept.
    """
    path = find_colors_path()
    if path is None:
        return {}

    colors = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if val.startswith("#") and len(val) == 7:
                    colors[key] = parse_hex(val)
    return colors


def read_theme_accent():
    """Return the raw (unsaturated) accent colour as (r, g, b), or None."""
    return load_theme_colors().get("accent")


def read_theme_palette(max_colors):
    """Build a vivid animation palette from the theme.

    Returns (saturated_accent, palette). `palette` is a list of distinct,
    saturation-boosted colours drawn from `accent` + the bright terminal
    colours, deduplicated by hue, capped at `max_colors`, with the accent
    always first. Returns (None, None) if the theme has no accent.
    """
    colors = load_theme_colors()
    accent = colors.get("accent")
    if not accent:
        return None, None

    palette = []
    seen_hues = set()
    for key in PALETTE_KEYS:
        c = colors.get(key)
        if not c:
            continue
        h, s, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
        # Skip very desaturated (grey/white) and very dark colours.
        if s < 0.2 or v < 0.2:
            continue
        # Deduplicate by hue: 24 buckets = 15-degree resolution.
        hue_bucket = round(h * 24)
        if hue_bucket in seen_hues:
            continue
        seen_hues.add(hue_bucket)
        palette.append(saturate(*c))

    palette = palette[:max_colors]

    saturated_accent = saturate(*accent)
    if saturated_accent in palette:
        palette.remove(saturated_accent)
    palette.insert(0, saturated_accent)

    return saturated_accent, palette
