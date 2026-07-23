#!/usr/bin/env python3
"""Set GMMK 2 keyboard RGB to the current omarchy theme accent color.

Requires QMK firmware with the rgb_sync keymap flashed on the keyboard.
Communicates via Raw HID (usage page 0xFF60, usage 0x61).

Usage:
    python set_rgb.py              # Wave animation with theme colors
    python set_rgb.py --solid      # Solid accent color only
    python set_rgb.py ff6600       # Set explicit hex color (solid)
    python set_rgb.py 255 100 0    # Set explicit R G B (solid)
    python set_rgb.py --query      # Query current keyboard state
"""

import os
import sys

# Import the shared omarchy theme helpers from the repo root. Resolved from this
# file's own location so it works when run by absolute path from the hook.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from omarchy_theme import parse_hex, read_theme_palette

try:
    import hid
except ImportError:
    print("Error: hid not installed. Run: pip install hid")
    sys.exit(1)

VID = 0x320F
PID = 0x504B
RAW_HID_USAGE_PAGE = 0xFF60
RAW_HID_USAGE = 0x61
PACKET_SIZE = 32

CMD_SET_COLOR = 0x01
CMD_QUERY = 0x02
CMD_SET_PALETTE = 0x03

# Firmware accepts at most 8 colors in a palette packet.
MAX_PALETTE = 8


def find_raw_hid_device():
    """Find the Raw HID interface of the GMMK 2."""
    for dev in hid.enumerate(VID, PID):
        if dev["usage_page"] == RAW_HID_USAGE_PAGE and dev["usage"] == RAW_HID_USAGE:
            return dev["path"]
    return None


def open_raw_hid():
    """Open the Raw HID device and return it."""
    path = find_raw_hid_device()
    if not path:
        print(f"Error: GMMK 2 Raw HID interface not found (VID={VID:#06x}, PID={PID:#06x})")
        print("Make sure the rgb_sync QMK firmware is flashed.")
        sys.exit(1)
    device = hid.Device(path=path)
    return device


def send_color(r, g, b):
    """Send a solid RGB color to the keyboard."""
    device = open_raw_hid()
    try:
        packet = bytes([0x00, CMD_SET_COLOR, r, g, b] + [0x00] * (PACKET_SIZE - 4))
        device.write(packet)

        response = device.read(PACKET_SIZE, timeout=1000)
        if response and response[0] == CMD_SET_COLOR:
            print(f"Set keyboard RGB to ({r}, {g}, {b}) / #{r:02x}{g:02x}{b:02x}")
        else:
            print(f"Sent color ({r}, {g}, {b}) but got unexpected response: {list(response)}")
    finally:
        device.close()


def send_palette(colors, speed=40):
    """Send a palette of colors for wave animation."""
    if len(colors) > MAX_PALETTE:
        colors = colors[:MAX_PALETTE]

    device = open_raw_hid()
    try:
        data = [0x00, CMD_SET_PALETTE, speed, len(colors)]
        for r, g, b in colors:
            data.extend([r, g, b])
        # Pad to full packet size
        data.extend([0x00] * (PACKET_SIZE + 1 - len(data)))
        device.write(bytes(data))

        response = device.read(PACKET_SIZE, timeout=1000)
        if response and response[0] == CMD_SET_PALETTE:
            print(f"Wave animation started with {response[1]} colors (speed={speed})")
            for i, (r, g, b) in enumerate(colors):
                print(f"  [{i}] #{r:02x}{g:02x}{b:02x}")
        else:
            print(f"Unexpected response: {list(response)}")
    finally:
        device.close()


def query_color():
    """Query the current state from the keyboard."""
    device = open_raw_hid()
    try:
        packet = bytes([0x00, CMD_QUERY] + [0x00] * (PACKET_SIZE - 1))
        device.write(packet)

        response = device.read(PACKET_SIZE, timeout=1000)
        if response and response[0] == CMD_QUERY:
            r, g, b = response[1], response[2], response[3]
            active = "yes" if response[4] else "no"
            animating = "yes" if response[5] else "no"
            num_colors = response[6]
            print(f"Color: ({r}, {g}, {b}) / #{r:02x}{g:02x}{b:02x}")
            print(f"Host-set: {active}, Animating: {animating}, Palette size: {num_colors}")
        else:
            print(f"Unexpected response: {list(response)}")
    finally:
        device.close()


def parse_hex_color(hex_str):
    """Parse and validate a hex color string."""
    c = parse_hex(hex_str)
    if not c:
        print(f"Error: Invalid hex color '{hex_str}' (expected 6 hex digits)")
        sys.exit(1)
    return c


def theme_palette():
    """Read the theme palette, exiting with an error if the theme is missing."""
    accent, palette = read_theme_palette(MAX_PALETTE)
    if not accent:
        print("Error: could not read omarchy theme accent color")
        sys.exit(1)
    return accent, palette


def main():
    args = sys.argv[1:]

    if not args:
        # Default: wave animation with theme colors
        _, palette = theme_palette()
        send_palette(palette, speed=200)
    elif args[0] == "--solid":
        accent, _ = theme_palette()
        send_color(*accent)
    elif args[0] == "--query":
        query_color()
    elif len(args) == 1:
        r, g, b = parse_hex_color(args[0])
        send_color(r, g, b)
    elif len(args) == 3:
        r, g, b = int(args[0]), int(args[1]), int(args[2])
        if not all(0 <= v <= 255 for v in (r, g, b)):
            print("Error: RGB values must be 0-255")
            sys.exit(1)
        send_color(r, g, b)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
