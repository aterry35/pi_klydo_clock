# Community Design Guide

This clock can load community-created dial and pendulum designs from folders on
the Raspberry Pi. A power cycle or renderer restart is enough for the app to
rescan the folders and include new designs.

Design folders do not carry device positions. Circle centers, enclosure geometry,
allowed diameters, and output asset limits live in `config/clock.json`, so one
calibration applies to every community design.

The hosted designer also has a Community page. Anyone can browse and download
published designs. An artist account is required to publish, like, or comment.
The exported ZIP format is the same whether it is downloaded locally or from the
gallery.

Signed-in users can report copyright concerns, inappropriate content, spam, broken
packages, or other issues from the design detail view. Reports enter the private
administrator queue. Hidden designs disappear from all public lists, previews, and
downloads but remain available to administrators for review and restoration.

## Where To Put Designs

The renderer scans these locations at startup:

```text
/opt/piclock/designs/              built-in/system designs
/boot/firmware/piclock-designs/    SD-card copy location
/boot/piclock-designs/             fallback for older Raspberry Pi OS images
~/piclock-designs/                 SCP/network-copy location
```

For this Pi, the SCP path is:

```text
/home/terry/piclock-designs/
```

Use one of these workflows.

## SD Card Copy Workflow

1. Shut down the Pi.
2. Remove the SD card and mount it on a computer.
3. Open the visible boot partition.
4. Create this folder if it does not exist:

   ```text
   piclock-designs/
   ```

5. Copy complete design folders into it.
6. Put the SD card back in the Pi and power on.

Example final SD-card layout:

```text
piclock-designs/
  sunny-kitchen/
    loop.mp4
    pendulum.png
    theme.json
  blue-orbit/
    loop.mp4
    pendulum.png
    theme.json
```

## SCP Workflow

Copy a finished design folder over the network:

```bash
scp -r sunny-kitchen terry@192.168.1.217:/home/terry/piclock-designs/
```

Then restart the renderer or power-cycle the Pi:

```bash
ssh terry@192.168.1.217
sudo systemctl restart piclock-renderer
```

## Required Folder Format

Each design must be one folder:

```text
<design-slug>/
  loop.mp4
  pendulum.png
  theme.json
```

Use a unique folder slug such as `sunny-kitchen`, `blue-orbit`, or
`paper-bloom`. Folder slugs are compared without regard to letter case. If a
user design has the same slug as a built-in design, the user design overrides
the built-in version. The SCP location is scanned last and therefore has the
highest priority when the same slug exists in multiple user locations.

New folders become available after the next renderer start. An existing manual
selection is preserved, so copying a folder does not automatically replace the
currently displayed design; tap or swipe the top circle to cycle to it.

## Dial Animation

File:

```text
loop.mp4
```

Requirements:

- 480 x 480 pixels.
- H.264 MP4 is preferred.
- 15 fps is preferred for Raspberry Pi 3.
- 4 to 10 seconds is preferred.
- Seamless or near-seamless loop.
- No audio track needed.
- Keep file size modest; under 20 MB is a good target.

The clock draws the real-time hands over this animation, so the animation
should not include clock hands unless that is intentional.

## Pendulum Art

File:

```text
pendulum.png
```

Requirements:

- Transparent PNG.
- 300 x 400 pixels recommended.
- Pivot point at the top center of the image.
- The app rotates this artwork live, so the pendulum image should be drawn
  straight down in its neutral center position.

SVG pendulums are also supported as `pendulum.svg`, but PNG is the safest
format for community submissions.

## Theme File

File:

```text
theme.json
```

Example:

```json
{
  "name": "Sunny Kitchen",
  "creator": {
    "artist": "A. Artist",
    "watermark": "A. Artist",
    "watermark_enabled": true,
    "watermark_color": "#ffffff",
    "watermark_opacity": 0.65
  },
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
    "count": 12,
    "diameter": 400
  },
  "pendulum": {
    "period_s": 1.6,
    "amplitude_deg": 9,
    "pivot": [0.5, 0.035],
    "rod_length": 0.74
  },
  "bottom": {
    "backdrop": "solid",
    "color": "#000000",
    "diameter": 300
  },
  "ambiance": {
    "day_night": false,
    "twinkle": false,
    "glow": false
  }
}
```

Useful values:

- `hands.hour` and `hands.minute` control the real clock hands.
- `creator.artist` identifies the artist in the gallery and package metadata.
- `creator.watermark` is rendered on the upper dial by the Pi clock. Community
  publishing requires the watermark to be enabled.
- Set `hands.second.visible` to `false` for a clean art-clock face.
- `shape` can be `rounded` or `spindle`.
- `dial.markings` can be `none`, `ticks`, `numerals`, or `both`.
- `dial.diameter` controls the upper background circle from 400 to 500 pixels.
- `bottom.backdrop` can be `loop`, `solid`, or `none`.
- `bottom.diameter` controls the pendulum background circle from 260 to 340 pixels.
- `pendulum.period_s` controls swing speed.
- `pendulum.amplitude_deg` controls swing width.

## Validate Before Copying

From the project folder:

```bash
python scripts/validate_design.py designs/sunny-kitchen
```

On the Pi:

```bash
cd /opt/piclock
.venv/bin/python scripts/validate_design.py /home/terry/piclock-designs/sunny-kitchen
```

The validator checks for the required files, JSON format, video size, and
pendulum image basics. It reads the same clock configuration as the renderer;
use `--config /path/to/override.json` to validate against an additional override.

## Expected Final Output From A Designer

A designer should deliver one complete folder:

```text
sunny-kitchen/
  loop.mp4
  pendulum.png
  theme.json
```

Optional files such as `preview.png`, `source.psd`, or `notes.txt` are fine, but
the clock only needs `loop.mp4`, `pendulum.png`, and `theme.json`.

## Browser Design Creator

The local design editor is in:

```text
Tools/clock-design-creator-app/app/
```

See its `README.md` for run, build, validation, and browser compatibility
instructions. It exports the required folder directly as a ZIP file.
