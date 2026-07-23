#!/usr/bin/env python3
"""Set Glorious Model D 2 Wireless RGB to the current omarchy theme palette.

Mirrors the GMMK 2 keyboard behaviour: by default, animates a multi-color
palette derived from the theme; --solid sets one accent color.

Usage:
    python set_rgb.py              # multi-color breathing with theme palette
    python set_rgb.py --solid      # solid accent color only
    python set_rgb.py ff6600       # explicit hex color (solid)
    python set_rgb.py 255 100 0    # explicit R G B (solid)
    python set_rgb.py --off        # LEDs off (single color = #000000)
    python set_rgb.py --probe      # passive readback diagnostic

Exits 0 silently when the mouse isn't connected, so the omarchy theme-set
hook stays clean when the mouse has been swapped out.
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
    print("glorious-mouse: 'hid' not installed (pip install hid). Skipping.")
    sys.exit(0)

VID = 0x093A
PID = 0x824A
VENDOR_USAGE_PAGE = 0xFF00
VENDOR_USAGE = 0x01
REPORT_ID = 0x03
PACKET_LEN = 32

# Captured packet structure (32-byte SET_FEATURE on Report 3, RE'd from
# Glorious Core USB traces — see notes.md):
#
#   offset 0:    0x03               report ID
#   offset 1-3:  0x02 0xfa 0x01     constant preamble
#   offset 4:    mode               0x04 = single, 0x05 = breathing-7-color,
#                                   0x01 = glorious, 0x08 = wave
#   offset 5-6:  0x0a 0x0c          speed bytes (defaults; we don't tune)
#   offset 7:    color count        0x01 for single, 0x07 for breathing
#   offset 8-9:  0x0a 0x0c          repeat of speed bytes
#   offset 10-15: 0x00              padding
#   offset 16+:  RGB triplets       1 for single, 7 for breathing
#   offset (16 + 3*count) - 31: 0x00 padding

PACKET_HEADER = bytes.fromhex("0302fa01")  # bytes 0..3
PACKET_TAIL_PADDING_OFFSET = 16
MODE_SINGLE = 0x04
# Mode 0x03 = multi-color breathing — cycles through user-supplied RGB
# colors at bytes 16+. Discovered by sweeping mode bytes after Glorious
# Core's "breathing single color" capture (mode 0x05) turned out to use
# only the first color slot. Verified by sending [red, green, blue] and
# watching the mouse cycle through exactly those colors.
MODE_BREATHING = 0x03
# 32-byte packet has room for 5 RGB triplets at bytes 16-30. Byte 31 stays
# zero. Core's captures included extra slots in the leading bytes (count=7)
# but only 5 fit in the wire payload — that's our real cap.
MAX_PALETTE = 5

# Bytes 5,6,8,9 are constants observed in every Core capture; values 0x0a/0x0c
# are likely default speed parameters. We send them verbatim until we have
# reason to vary them.
SPEED_DEFAULT_A = 0x0a
SPEED_DEFAULT_B = 0x0c


def find_vendor_path():
    """Return the hidraw path of the vendor-page interface, or None."""
    for d in hid.enumerate(VID, PID):
        if d["usage_page"] == VENDOR_USAGE_PAGE and d["usage"] == VENDOR_USAGE:
            return d["path"]
    return None


def open_device(retries=5, delay=1.0):
    """Open the vendor interface, retrying briefly to handle autostart races.

    The wireless dongle can take several seconds to enumerate after login —
    Hyprland's exec-once fires before that's done, so an immediate lookup
    sees no device. Retry up to `retries` times before giving up silently.
    """
    import time
    for _ in range(retries):
        path = find_vendor_path()
        if path:
            try:
                return hid.Device(path=path)
            except Exception as e:
                print(f"glorious-mouse: failed to open {path!r}: {e}")
                return None
        time.sleep(delay)
    return None


def _build_packet(mode, colors):
    """Build the 32-byte SET_FEATURE payload for a given mode and color list."""
    pkt = bytearray(PACKET_LEN)
    pkt[0] = REPORT_ID
    pkt[1:4] = PACKET_HEADER[1:]  # 02 fa 01 (PACKET_HEADER includes the 0x03)
    pkt[4] = mode
    pkt[5] = SPEED_DEFAULT_A
    pkt[6] = SPEED_DEFAULT_B
    pkt[7] = len(colors) & 0xff
    pkt[8] = SPEED_DEFAULT_A
    pkt[9] = SPEED_DEFAULT_B
    # bytes 10-15 stay zero
    off = PACKET_TAIL_PADDING_OFFSET
    for r, g, b in colors[:MAX_PALETTE]:
        pkt[off] = r & 0xff
        pkt[off + 1] = g & 0xff
        pkt[off + 2] = b & 0xff
        off += 3
    return bytes(pkt)


def _send(dev, packet):
    try:
        dev.send_feature_report(packet)
        return True
    except Exception as e:
        print(f"glorious-mouse: send_feature_report failed: {e}")
        return False


def send_color(dev, r, g, b):
    """Single-color mode: solid RGB."""
    return _send(dev, _build_packet(MODE_SINGLE, [(r, g, b)]))


def send_palette(dev, colors):
    """Breathing-multicolor mode: cycle through up to 7 RGB colors."""
    if not colors:
        return False
    return _send(dev, _build_packet(MODE_BREATHING, list(colors)))


def cmd_probe(dev):
    """Read back the device's current state (passive, safe)."""
    try:
        buf = bytes(dev.get_feature_report(REPORT_ID, PACKET_LEN))
    except Exception as e:
        print(f"glorious-mouse: probe read failed: {e}")
        return
    print(f"glorious-mouse: report {REPORT_ID:#04x} ({len(buf)} bytes): {buf.hex()}")


def main():
    args = sys.argv[1:]

    dev = open_device()
    if dev is None:
        # Mouse not present — exit silently (graceful for theme-hook context).
        return

    try:
        if args and args[0] == "--probe":
            cmd_probe(dev)
            return

        if args and args[0] == "--mode":
            # Debug: send our theme palette with an arbitrary mode byte.
            # Used to discover which mode values cycle colors vs hold static.
            if len(args) < 2:
                print("usage: --mode <hex>  (e.g. --mode 0x03)")
                sys.exit(1)
            try:
                mode = int(args[1], 0)
            except ValueError:
                print(f"glorious-mouse: bad mode {args[1]!r}")
                sys.exit(1)
            _, palette = read_theme_palette(MAX_PALETTE)
            if not palette:
                palette = [(0xff, 0, 0), (0, 0xff, 0), (0, 0, 0xff),
                           (0xff, 0xff, 0), (0xff, 0, 0xff)]
            pkt = _build_packet(mode, palette)
            if _send(dev, pkt):
                print(f"glorious-mouse: sent mode {mode:#04x} with {len(palette)} colors")
            return

        if args and args[0] == "--off":
            send_color(dev, 0, 0, 0)
            print("glorious-mouse: off")
            return

        if args and args[0] == "--solid":
            accent, _ = read_theme_palette(MAX_PALETTE)
            if not accent:
                print("glorious-mouse: no theme accent found, skipping.")
                return
            if send_color(dev, *accent):
                print(f"glorious-mouse: solid #{accent[0]:02x}{accent[1]:02x}{accent[2]:02x}")
            return

        if len(args) == 1:
            color = parse_hex(args[0])
            if not color:
                print(f"glorious-mouse: invalid hex {args[0]!r}")
                sys.exit(1)
            if send_color(dev, *color):
                print(f"glorious-mouse: solid #{color[0]:02x}{color[1]:02x}{color[2]:02x}")
            return

        if len(args) == 3:
            try:
                color = tuple(int(x) for x in args)
            except ValueError:
                print("glorious-mouse: R G B must be integers 0-255")
                sys.exit(1)
            if not all(0 <= v <= 255 for v in color):
                print("glorious-mouse: R G B must be 0-255")
                sys.exit(1)
            if send_color(dev, *color):
                print(f"glorious-mouse: solid #{color[0]:02x}{color[1]:02x}{color[2]:02x}")
            return

        # Default: multi-color breathing palette from theme
        accent, palette = read_theme_palette(MAX_PALETTE)
        if not palette:
            print("glorious-mouse: no theme palette found, skipping.")
            return
        if send_palette(dev, palette):
            colors_hex = " ".join(f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette)
            print(f"glorious-mouse: breathing palette ({len(palette)} colors): {colors_hex}")
    finally:
        dev.close()


if __name__ == "__main__":
    main()
