#!/usr/bin/env python3
"""Set Logitech G903 mouse RGB to the current omarchy theme accent color.

Uses ratbagctl (libratbag) to control the mouse LEDs via HID++ 2.0.

Usage:
    python set_rgb.py              # Static accent color on both LEDs
    python set_rgb.py --breathing  # Breathing effect with accent color
    python set_rgb.py --cycle      # Color cycle mode
    python set_rgb.py --off        # Turn LEDs off
    python set_rgb.py ff6600       # Set explicit hex color (static)
    python set_rgb.py 255 100 0    # Set explicit R G B (static)
"""

import os
import subprocess
import sys

# Import the shared omarchy theme helpers from the repo root. Resolved from this
# file's own location so it works when run by absolute path from the hook.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from omarchy_theme import parse_hex, saturate, read_theme_accent


def find_device():
    """Find the G903 device name from ratbagctl, or None if not present."""
    try:
        result = subprocess.run(["ratbagctl", "list"], capture_output=True, text=True)
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.strip().splitlines():
        if ":" in line:
            return line.split(":")[0].strip()
    return None


def set_led(device, led_index, mode, color=None):
    """Set a single LED's mode and optionally color."""
    prefix = ["ratbagctl", device, "profile", "0", "led", str(led_index), "set"]

    subprocess.run(prefix + ["mode", mode], capture_output=True, text=True, check=True)

    if color and mode in ("on", "breathing"):
        hex_color = f"{color[0]:02x}{color[1]:02x}{color[2]:02x}"
        subprocess.run(prefix + ["color", hex_color], capture_output=True, text=True, check=True)


def set_all_leds(device, mode, color=None):
    """Set both LEDs to the same mode and color."""
    for i in range(2):
        set_led(device, i, mode, color)


def theme_accent():
    """Return the saturated theme accent, exiting if the theme is missing."""
    accent = read_theme_accent()
    if not accent:
        print("Error: could not read omarchy theme accent color")
        sys.exit(1)
    return saturate(*accent)


def main():
    args = sys.argv[1:]
    device = find_device()
    if device is None:
        # G903 not connected — skip silently so the omarchy theme-set hook
        # stays clean when the mouse has been swapped out.
        return

    if not args:
        # Default: static accent color
        accent = theme_accent()
        set_all_leds(device, "on", accent)
        print(f"Set mouse LEDs to accent #{accent[0]:02x}{accent[1]:02x}{accent[2]:02x}")
    elif args[0] == "--breathing":
        accent = theme_accent()
        set_all_leds(device, "breathing", accent)
        print(f"Breathing mode with #{accent[0]:02x}{accent[1]:02x}{accent[2]:02x}")
    elif args[0] == "--cycle":
        set_all_leds(device, "cycle")
        print("Color cycle mode")
    elif args[0] == "--off":
        set_all_leds(device, "off")
        print("LEDs off")
    elif len(args) == 1:
        color = parse_hex(args[0])
        if not color:
            print(f"Error: Invalid hex color '{args[0]}' (expected 6 hex digits)")
            sys.exit(1)
        set_all_leds(device, "on", color)
        print(f"Set mouse LEDs to #{color[0]:02x}{color[1]:02x}{color[2]:02x}")
    elif len(args) == 3:
        r, g, b = int(args[0]), int(args[1]), int(args[2])
        if not all(0 <= v <= 255 for v in (r, g, b)):
            print("Error: RGB values must be 0-255")
            sys.exit(1)
        set_all_leds(device, "on", (r, g, b))
        print(f"Set mouse LEDs to ({r}, {g}, {b})")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
