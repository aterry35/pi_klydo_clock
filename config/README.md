# Clock Configuration

`clock.json` is the shared source of truth for device-wide rendering and design
package limits. Both the native clock renderer and the browser designer read it.

The calibrated Pi layout and the browser preview use separate center settings.
This keeps artwork centered in the designer without changing its alignment with
the physical enclosure on the clock.

## Configuration Levels

The clock deliberately uses two JSON levels:

- `clock.json` controls the physical device: display, circle positions, size
  limits, enclosure measurements, design folders, and asset requirements.
- Each design folder's `theme.json` controls its artwork: hands, dial markings,
  circle diameter within the allowed range, pendulum motion, and colors.

Physical registration does not belong in every design. Changing a center in
`clock.json` moves every installed design together.

## Load Order

The renderer merges these files in order. Later values override earlier values:

1. `/opt/piclock/config/clock.json` (installed project defaults)
2. `/etc/piclock/clock.json` (persistent device calibration)
3. `/boot/piclock-config.json` (older Raspberry Pi OS boot partition)
4. `/boot/firmware/piclock-config.json` (Bookworm boot partition)
5. Any file passed with `--config`

The installer initializes `/etc/piclock/clock.json` from
`device-clock.example.json` only when the device file does not already exist.
Subsequent installs preserve the device calibration.

Override files may contain only the fields that need changing. For example:

```json
{
  "layout": {
    "dial": { "center": [224, 260] },
    "pendulum": { "center": [210, 650] }
  }
}
```

After changing a file on the Pi, restart the renderer:

```bash
sudo systemctl restart piclock-renderer
```

Invalid override files are reported in the service journal and ignored so that
a malformed SD-card configuration cannot stop the clock from booting.

## Main Fields

| JSON path | Purpose |
|---|---|
| `display.mode` | `kms` on the Pi or `windowed` for desktop use. |
| `display.width`, `display.height` | Portrait render canvas. |
| `display.rotate`, `display.touch_rotate` | Display and touch orientation. |
| `display.circle_y_scale` | Physical pixel aspect correction. |
| `layout.dial.center` | Upper circle center `[x, y]` in canvas pixels. |
| `layout.pendulum.center` | Lower circle center `[x, y]` in canvas pixels. |
| `designer.preview.dial_center` | Upper circle center used only by the browser designer and exported preview image. |
| `designer.preview.pendulum_center` | Lower circle center used only by the browser designer and exported preview image. |
| `network.enabled` | Enables the on-device long-press network recovery panel. |
| `network.interface` | NetworkManager Wi-Fi device controlled by the helper. |
| `network.control_socket` | Renderer/helper Unix socket under `/run/piclock-network`. |
| `network.long_press_seconds` | Stationary upper-dial hold duration required to open recovery. |
| `network.max_visible_networks` | Number of nearby SSIDs shown inside the dial. |
| `layout.*.minimum_diameter` | Smallest diameter accepted from `theme.json`. |
| `layout.*.default_diameter` | Default and designer starting diameter. |
| `layout.*.maximum_diameter` | Largest accepted/designer diameter. |
| `designs.system_directory` | Built-in design folder. |
| `designs.user_directories` | Ordered SD-card/SCP scan folders. |
| `designs.state_path` | Persisted manual/daily selection. |
| `designs.assets` | Export canvas, frame-rate, and duration requirements. |
| `enclosure` | CAD reference measurements in millimeters. |

Command-line geometry options remain available for temporary diagnosis, but
production calibration should be saved in a JSON override.

The default browser preview centers both circles at `x = 240` on the 480 px
canvas. The Pi keeps its enclosure-calibrated centers under `layout`; changing
the `designer.preview` values does not move installed clock designs.

Network recovery values are device-wide. If `control_socket` is overridden, the
root helper only accepts paths directly under `/run/piclock-network`; this prevents
an SD-card override from replacing arbitrary system files.
