# omarchy-rgb-sync

Sync the RGB lighting on your peripherals to the active [omarchy](https://omarchy.org)
desktop theme — automatically, every time you switch themes.

When you run `omarchy theme set ...` (or cycle themes from the menu), omarchy
fires a `theme-set` hook. This repo hooks into that event and pushes the new
theme's **accent color** (and a saturation-boosted palette derived from it) to
each supported device. It also runs once at login via Hyprland autostart so
your lighting matches from the moment you log in.

One shared module reads the theme; each device has a small driver that speaks
its own protocol.

## Supported devices

| Device | Transport | Mechanism | Requires |
|--------|-----------|-----------|----------|
| Glorious GMMK 2 (96% ANSI) keyboard | QMK Raw HID (usage page `0xFF60`) | Custom `rgb_sync` QMK keymap; animated color-wave palette | Custom QMK firmware flashed (see below), `python-hid` |
| Logitech G903 mouse | libratbag / HID++ 2.0 | `ratbagctl` sets both LEDs to the accent | `ratbagd` / libratbag |
| Glorious Model D 2 Wireless mouse | hidapi feature report (reverse-engineered) | Multi-color breathing palette | `python-hid` |
| Alienware Aurora R7 case | `acpi_call` → WMAX WMI method `0x12` | Sets all case zones to the accent | `acpi_call` kernel module + passwordless sudo for `/proc/acpi/call` |

Each driver **exits cleanly (and silently) when its device isn't connected**, so
the shared hook stays quiet whether or not a given peripheral is plugged in.

> **Note:** omarchy 4 ships its own theme keyboard-RGB support, but only for
> ASUS ROG and Framework 16 keyboards. These drivers cover hardware omarchy
> doesn't, and drive them over their native protocols.

## How it works

```
omarchy theme set <name>
        │
        ├─ writes ~/.local/state/omarchy/current/theme/colors.toml
        └─ runs the theme-set hook
                │
                └─ hooks/theme-set  ──►  <device>/set_rgb.py  (one per device)
                                              │
                                              └─ omarchy_theme.py reads colors.toml,
                                                 builds a vivid palette, drives the device
```

- **`omarchy_theme.py`** — shared: locates and parses the active theme's
  `colors.toml` (tries the omarchy 4 `~/.local/state/...` path first, falls back
  to the legacy `~/.config/...` path), boosts saturation for LED output, and
  builds a hue-deduplicated palette with the accent first.
- **`<device>/set_rgb.py`** — per-device driver. Run with no arguments it syncs
  to the theme; each also takes an explicit color and device-specific flags.

## Install

```bash
git clone https://github.com/scottjones/omarchy-rgb-sync.git ~/code/personal/omarchy-rgb-sync
pip install hid          # for the GMMK 2 keyboard and Glorious mouse drivers
```

Then set up the per-device prerequisites you need (see the table above), and
wire up the two triggers:

**1. Theme-change hook** (fires on every theme switch):

```bash
omarchy hook install theme-set ~/code/personal/omarchy-rgb-sync/hooks/theme-set
```

**2. Login autostart** (matches your lighting at login) — add to
`~/.config/hypr/autostart.lua`:

```lua
o.exec_on_start("/home/YOU/code/personal/omarchy-rgb-sync/keyboard-gmmk2/set_rgb.py")
o.exec_on_start("/home/YOU/code/personal/omarchy-rgb-sync/mouse-logitech-g903/set_rgb.py")
o.exec_on_start("/home/YOU/code/personal/omarchy-rgb-sync/mouse-glorious-model-d2/set_rgb.py")
o.exec_on_start("/home/YOU/code/personal/omarchy-rgb-sync/case-alienware-aurora-r7/set_rgb.py")
```

> The scripts need the system Python (which sees pacman-installed `python-hid`
> and libratbag), not a mise/pyenv shim. `hooks/theme-set` forces
> `PATH=/usr/bin:$PATH` for this reason; the autostart entries run the scripts
> directly, so make sure `/usr/bin/env python3` resolves to system Python there.

## Usage

Run any driver directly to test it. With no arguments it syncs to the current
theme; all drivers also accept an explicit `rrggbb` hex or `R G B` triplet.

```bash
# Keyboard — wave animation (default), solid accent, explicit color, or query
keyboard-gmmk2/set_rgb.py
keyboard-gmmk2/set_rgb.py --solid
keyboard-gmmk2/set_rgb.py ff6600
keyboard-gmmk2/set_rgb.py --query

# Logitech G903 — static accent (default), breathing, cycle, off
mouse-logitech-g903/set_rgb.py
mouse-logitech-g903/set_rgb.py --breathing
mouse-logitech-g903/set_rgb.py --off

# Glorious Model D 2 — breathing palette (default), solid accent, off, probe
mouse-glorious-model-d2/set_rgb.py
mouse-glorious-model-d2/set_rgb.py --solid
mouse-glorious-model-d2/set_rgb.py --probe

# Alienware case — accent (default), explicit color, off
case-alienware-aurora-r7/set_rgb.py
case-alienware-aurora-r7/set_rgb.py --off
```

### GMMK 2 keyboard: QMK firmware

The keyboard driver talks to a custom QMK `rgb_sync` keymap over Raw HID, not
the stock Glorious firmware (whose proprietary protocol freezes the board).

- **Build:** `qmk compile -kb gmmk/gmmk2/p96/ansi -km rgb_sync`
- **Flash:** enter the bootloader (hold **Spacebar + B** while plugging in USB),
  then `qmk flash -kb gmmk/gmmk2/p96/ansi -km rgb_sync`
- **Recover:** if anything goes wrong, re-enter the bootloader (Spacebar + B)
  and flash the stock Glorious Core `.hex` to restore.

Raw HID protocol (32-byte packets): `0x01 R G B` sets a solid color,
`0x03 speed count [R G B]...` sets a wave palette, `0x02` queries current state.

## Repository layout

```
omarchy-rgb-sync/
├── omarchy_theme.py              # shared theme color reader + palette builder
├── hooks/theme-set               # installable omarchy theme-set hook
├── keyboard-gmmk2/set_rgb.py
├── mouse-logitech-g903/set_rgb.py
├── mouse-glorious-model-d2/set_rgb.py
└── case-alienware-aurora-r7/set_rgb.py
```

## License

MIT — see [LICENSE](LICENSE).
