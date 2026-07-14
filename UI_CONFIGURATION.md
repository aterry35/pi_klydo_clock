# UI Configuration Guide

This project is designed so the clock UI can grow by adding **design folders**,
not by editing renderer code for every new clock face.

## What Is Configurable Today

The renderer currently supports:

- multiple designs stored in one directory;
- daily automatic design selection;
- manual design override by touch/swipe or keyboard;
- persisted selected design state;
- per-design video loop artwork;
- per-design pendulum artwork;
- per-design hands, dial markings, pendulum motion, and ambiance settings.

Device-wide geometry and package limits are configured in `config/clock.json`.
Per-design artwork remains in each design folder's `theme.json`. This separation
means one enclosure correction applies to every built-in and user design.

The default production location on the Pi is:

```text
/opt/piclock/designs/
```

User/community designs are also scanned on startup from:

```text
/boot/firmware/piclock-designs/    SD-card copy location
/boot/piclock-designs/             older Raspberry Pi OS fallback
~/piclock-designs/                 SCP/network-copy location
```

The local development location is:

```text
designs/
```

Each design is one folder:

```text
designs/<design-name>/
  loop.mp4 | loop.webm | loop.mkv
  pendulum.png | pendulum.svg
  theme.json
```

The app scans these directories at startup. If you add a new design while the
app is already running, restart `piclock-renderer` so it rescans the folder
list.

## Screen Geometry

The target display is the 7" DSI panel in portrait:

```text
screen: 480 x 800
top circle: 400 px diameter
bottom circle: 300 px diameter
software fixture border: 0 px (the printed face supplies the border)
```

The default layout is registered to the measured 102 x 165 mm enclosure:

```text
dial aperture:      76 mm diameter, starts at x=14.9954 mm, y=16.4983 mm
pendulum aperture:  48.5 mm diameter, starts at x=29.0742 mm, y=107.4681 mm
```

These are enclosure coordinates. Do not convert them directly using 102 mm =
480 px or 165 mm = 800 px because the LCD active area is inset within the
physical panel. The currently calibrated renderer centers are `(224,260)` and
`(210,650)`. Edit `layout.dial.center` and `layout.pendulum.center` in
`/etc/piclock/clock.json` or an SD-card override for future registration changes.
Exported design folders intentionally do not contain device layout offsets. See
`config/README.md` for every clock-wide field and override precedence.

Recommended artwork sizes:

```text
loop video:      480 x 480 maximum, 400 x 400 also acceptable
pendulum image: 300 x 400, transparent background, pivot at top center
```

Keep important artwork inside the physical cutout, but let the background fill
the complete exported frame. The renderer overscans the openings so mounting
tolerance and the 2 mm enclosure depth cannot reveal a software-painted black ring.

## theme.json Schema

Minimal example:

```json
{
  "name": "Kitchen Pop",
  "accent": "#ffb70f",
  "background": "#050505",
  "hands": {
    "hour": {
      "color": "#063d3a",
      "width": 11,
      "length": 0.42,
      "glow": false,
      "shape": "rounded"
    },
    "minute": {
      "color": "#063d3a",
      "width": 9,
      "length": 0.66,
      "glow": false,
      "shape": "rounded"
    },
    "second": {
      "color": "#ffb70f",
      "width": 2,
      "length": 0.85,
      "glow": false,
      "visible": false
    }
  },
  "dial": {
    "markings": "none",
    "color": "#ffffff",
    "count": 12
  },
  "pendulum": {
    "period_s": 1.6,
    "amplitude_deg": 9,
    "pivot": [0.5, 0.035],
    "rod_length": 0.74
  },
  "bottom": {
    "backdrop": "loop",
    "color": "#050505"
  },
  "ambiance": {
    "day_night": false,
    "twinkle": false,
    "glow": false
  }
}
```

### Top-Level Fields

| Field | Purpose |
|---|---|
| `name` | Human-readable design name and persisted selection key. |
| `accent` | Hub, pendulum, and fallback color. |
| `background` | Used for the hand hub center and non-day-night fallback. |
| `hands` | Hour/minute/second hand styling. |
| `dial` | Tick/numeral visibility and color. |
| `pendulum` | Swing motion and pivot. |
| `bottom` | Lower cutout backdrop behind the pendulum. |
| `ambiance` | Optional real-time tint/twinkle overlay. |

### Hands

| Field | Meaning |
|---|---|
| `color` | Hex color. |
| `width` | Stroke/body width in pixels. |
| `length` | Fraction of the top-circle radius. |
| `glow` | Adds soft glow when true. |
| `visible` | Optional; set `false` to hide a hand. Useful for no second hand. |
| `shape` | `spindle` for pointed clock hands, `rounded` for Klydo-style baton hands. |

### Dial

| `markings` | Result |
|---|---|
| `none` | No marks. Best for artwork-led Klydo-style designs. |
| `ticks` | Hour tick marks. |
| `numerals` | 12/3/6/9 numerals with small dots. |
| `both` | Tick marks plus numerals/dots. |

### Pendulum

| Field | Meaning |
|---|---|
| `period_s` | Full left-right-left swing period in seconds. |
| `amplitude_deg` | Peak swing angle. |
| `pivot` | `[x, y]` fraction of the bottom circle bounding box. |
| `rod_length` | Fraction of bottom circle diameter used by procedural fallback. |

For custom pendulum art, use `pendulum.png` or `pendulum.svg` with a transparent
background. The pivot should be at the **top center** of the image.

### Bottom Backdrop

| `backdrop` | Result |
|---|---|
| `loop` | Reuses the top design loop behind the pendulum. This is the default. |
| `solid` | Draws a solid circular backdrop using `color`. |
| `none` | Leaves the lower cutout black before drawing the pendulum. |

## Design Selection Logic

The renderer has two selection modes.

### Daily Mode

Daily mode chooses a deterministic design from the design list based on the
current date. This gives a Klydo-like "new design each day" behavior without a
network connection.

The device JSON starts with:

```text
"startup_mode": "daily"
```

The code path is `DesignSet.daily()` / `DesignSet._select_daily()`.

### Manual Mode

Manual mode is entered when the user cycles designs:

- tap top circle: next design;
- swipe left/right on top circle: next/previous design;
- keyboard right/left: next/previous design;
- keyboard `d`: return to daily mode.

The chosen mode/design is persisted in the state file. On the Pi this is:

```text
/var/lib/piclock/state.json
```

Example:

```json
{
  "mode": "manual",
  "selected": "Kitchen Pop",
  "folder": "kitchen-pop"
}
```

To force daily mode again:

```json
{
  "mode": "daily",
  "selected": "Kitchen Pop",
  "folder": "kitchen-pop"
}
```

Then restart:

```bash
sudo systemctl restart piclock-renderer
```

## Physical Knob / GPIO Control

GPIO knob control is not implemented yet, but the app is already structured for
it. The renderer uses semantic actions:

```text
next_design
prev_design
daily_design
toggle_dim
quit
```

Current sources:

- touch;
- mouse for development;
- keyboard.

Recommended implementation for a rotary encoder:

1. Add a small GPIO input module or sidecar service.
2. Map clockwise to `next_design`.
3. Map counter-clockwise to `prev_design`.
4. Map button press to `daily_design` or `toggle_dim`.
5. Keep the renderer action API semantic so GPIO details do not leak into UI code.

For the Pi, a separate service can also write the state file and restart or
signal the renderer. A cleaner future version would add a local UNIX socket or
small HTTP endpoint so remote/GPIO controllers can send actions live.

## Remote Control Options

Remote control is also not implemented yet in the native renderer. The legacy
HTML had a WebSocket bridge, but that was removed with Chromium.

Reasonable future choices:

| Option | Use When |
|---|---|
| Local HTTP API | Phone/app/controller on same Wi-Fi should change design. |
| WebSocket | Need live remote commands without polling. |
| MQTT | Home automation integration. |
| File drop + restart | Simplest maintenance path; safe but not live. |
| GPIO sidecar | Physical knob/button only. |

Suggested API shape:

```text
POST /api/design/next
POST /api/design/prev
POST /api/design/daily
POST /api/design/select {"name": "Kitchen Pop"}
POST /api/dim {"enabled": true}
GET  /api/designs
```

## Adding A New Design Manually

1. Create a new folder:

   ```bash
   mkdir -p designs/my-design
   ```

2. Add a square loop:

   ```text
   designs/my-design/loop.mp4
   ```

3. Add pendulum art:

   ```text
   designs/my-design/pendulum.png
   ```

4. Add `theme.json`.

5. Test locally:

   ```bash
   cd src
   ../.venv/bin/python -m piclock.cli --windowed --designs ../designs \
     --state ../.piclock-state.json
   ```

6. Deploy to Pi:

   ```bash
   sudo rsync -a designs/my-design /opt/piclock/designs/
   sudo systemctl restart piclock-renderer
   ```

## AI Agent Design Contract

If an AI agent creates designs for this project, ask it to produce a complete
folder with this exact structure:

```text
designs/<slug>/
  loop.mp4
  pendulum.png
  theme.json
```

Constraints for generated designs:

- `loop.mp4`: square, 480x480 max, H.264, 12-15 fps, 4-8 seconds, seamless or
  near-seamless loop;
- keep important artwork inside the visible enclosure aperture;
- no clock hands or numerals baked into the video unless intentionally part of
  the artwork;
- `pendulum.png`: transparent, 300x400 recommended, pivot at top center;
- `theme.json`: must set hand colors, hand shape, dial markings, pendulum
  period/amplitude, and ambiance options;
- use `dial.markings: "none"` for artwork-led Klydo-style designs;
- use `hands.second.visible: false` when the design should feel clean and
  product-like.

Example prompt for an AI design agent:

```text
Create a Pi Klydo Clock design folder named "sunny-kitchen".
Target display is 480x800 with a 400px top circle and 300px bottom circle.
Produce:
- loop.mp4, 480x480, 15fps, 6 seconds, seamless, abstract flat artwork;
- pendulum.png, 300x400 transparent PNG, pivot at top center;
- theme.json using rounded dark hands, no dial markings, no second hand.
Keep important artwork inside the visible enclosure aperture.
Return files in designs/sunny-kitchen/.
```

## Current Limitations

- Designs are scanned at startup, not hot-loaded.
- Daily rotation is date-based and deterministic, not tied to downloaded content.
- Touch and keyboard selection work now; GPIO knob and remote API are planned
  extensions.
- The UI configuration is file-based, not an on-screen settings interface.
- Physical enclosure quality still matters: the black faceplate and wood frame
  are part of the final visual polish, not only software.
