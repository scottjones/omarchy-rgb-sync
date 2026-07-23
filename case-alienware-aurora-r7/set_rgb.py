#!/usr/bin/env python3
"""Set Alienware Aurora R7 case RGB to the current omarchy theme accent color.

Uses acpi_call to invoke the WMAX WMI method (method_id 0x12) which controls
the case LEDs via I2C. Requires the acpi_call kernel module and sudo access
to /proc/acpi/call.

Usage:
    python set_rgb.py              # Saturated accent color on all zones
    python set_rgb.py ff6600       # Set explicit hex color
    python set_rgb.py 255 100 0    # Set explicit R G B
    python set_rgb.py --off        # Turn LEDs off
"""

import os
import subprocess
import sys

# Import the shared omarchy theme helpers from the repo root. Resolved from this
# file's own location so it works when run by absolute path from the hook.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from omarchy_theme import parse_hex, saturate, read_theme_accent

ACPI_CALL_PATH = "/proc/acpi/call"

# WMAX method path in ACPI namespace
WMAX_PATH = r"\_SB.AMW1.WMAX"

# Zone bitmask: bit 0 = head, bit 1 = left/logo, bit 2 = right
ALL_ZONES = 0x07


def acpi_call(r, g, b, zones=ALL_ZONES, state=0xFF):
    """Call WMAX method 0x12 to set LED color."""
    # Buffer: {zone_mask, 0, 0, 0, blue, green, red, state}
    buf = f"{{{zones:#04x},0x00,0x00,0x00,{b:#04x},{g:#04x},{r:#04x},{state:#04x}}}"
    cmd = f"{WMAX_PATH} 0x00 0x12 {buf}"

    result = subprocess.run(
        ["sudo", "-n", "tee", ACPI_CALL_PATH],
        input=cmd, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"Error: Failed to write to {ACPI_CALL_PATH}: {result.stderr.strip()}")
        print("Ensure acpi_call module is loaded and sudoers is configured.")
        sys.exit(1)


def theme_accent():
    """Return the fully saturated theme accent, exiting if the theme is missing."""
    accent = read_theme_accent()
    if not accent:
        print("Error: could not read omarchy theme accent color")
        sys.exit(1)
    # Case LEDs look best at full brightness (min_value=1.0).
    return saturate(*accent, min_value=1.0)


def main():
    args = sys.argv[1:]

    if not args:
        # Default: saturated accent color
        accent = theme_accent()
        acpi_call(*accent)
        print(f"Set case LEDs to accent #{accent[0]:02x}{accent[1]:02x}{accent[2]:02x}")
    elif args[0] == "--off":
        acpi_call(0, 0, 0, state=0x00)
        print("Case LEDs off")
    elif len(args) == 1:
        color = parse_hex(args[0])
        if not color:
            print(f"Error: Invalid hex color '{args[0]}' (expected 6 hex digits)")
            sys.exit(1)
        acpi_call(*color)
        print(f"Set case LEDs to #{color[0]:02x}{color[1]:02x}{color[2]:02x}")
    elif len(args) == 3:
        r, g, b = int(args[0]), int(args[1]), int(args[2])
        if not all(0 <= v <= 255 for v in (r, g, b)):
            print("Error: RGB values must be 0-255")
            sys.exit(1)
        acpi_call(r, g, b)
        print(f"Set case LEDs to ({r}, {g}, {b})")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
