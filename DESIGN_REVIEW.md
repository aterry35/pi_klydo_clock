# Design Review - Pi Klydo Clock

## 1. Reference Target

The Klydoclock reference is not just an analog clock skin. It is closer to a
small media appliance: a circular animated artwork, analog hands rendered over
that artwork, and a changing content library/daily feed. The useful product
idea to copy is the separation of responsibilities:

- the animation is authored media;
- the clock hands are a live, correct time layer;
- designs are content packages, not code changes.

The physical target here is different from the commercial product: a Raspberry
Pi 3 with a 7" DSI panel in portrait, 480x800, behind a 3D-printed faceplate
with two circular cutouts. That means the fixture geometry matters as much as
the graphics.

## 2. Current Legacy HTML

The preserved legacy file at `legacy/Pi Clock.html` is a bundled React/x-dc
artifact, not maintainable hand-authored HTML/CSS:

- hands are DOM elements rotated with CSS transforms from `new Date()`;
- designs are hardcoded theme objects inside minified JavaScript;
- backgrounds are CSS gradients/keyframes, not external artwork packages;
- the pendulum exists, but period/amplitude are fixed in CSS;
- input is keyboard/WebSocket oriented, not touch-first;
- there is no RTC, provisioning, systemd, design-folder loading, or boot path.

The legacy version is visually useful and should remain as reference material,
but it is the wrong runtime for the appliance.

## 3. What To Keep

- Two-circle composition: large clock dial above, smaller pendulum below.
- Live analog hands over the design layer.
- Themed pendulum matched to the active design.
- Day/night/twinkle idea from the old implementation, but as a subtle live
  overlay inside the circular cutouts rather than a browser background.
- Keyboard cycle controls as a fallback.
- The black border/ring around the circles; it is useful for bezel alignment
  and hides small fixture tolerances.

## 4. What To Replace

- Chromium kiosk as the primary renderer.
- Hardcoded theme arrays and bundled JS assets.
- CSS-only "designs" as the final content model.
- Any boot path that waits for Wi-Fi before showing the clock.
- Any installer/service path that assumes the display user can be changed
  freely without validating DRM/KMS ownership on the actual Pi.

## 5. Renderer Decision

**Chosen path: native SDL2 via pygame-ce, with PyAV for small video loops.**

For this hardware revision the video loops are at most 480x480, not 1080p. That
removes the strongest reason to keep Chromium or a dedicated video player.

| Option | Verdict |
|---|---|
| Chromium kiosk | Visually close and easy for CSS, but slow cold start, high RAM use, browser/compositor complexity, and more moving parts at boot. |
| mpv/GStreamer with overlay | Strong video path, but hand/dial overlay synchronization becomes the hard part. It optimizes video decode while making the clock layer fragile. |
| Native SDL2 + PyAV | One process owns the frame loop, hands are structurally independent of the video, touch can be handled directly, and the app can be tested on the Mac before Pi deployment. |

This is still performance-sensitive on a Pi 3. The loops must stay small and
short, and the renderer should avoid per-frame scaling/allocations where
possible. The current app caches the lower-circle scaled frame while the source
video frame is unchanged.

## 6. Approved Architecture

The app now follows this model:

```text
designs/<name>/
  loop.mp4 | loop.webm | loop.mkv
  pendulum.png | pendulum.svg
  theme.json
```

At runtime:

1. Scan the design folders at startup.
2. Pick the daily design by default.
3. Let touch/swipe/keyboard select a manual design and persist it.
4. Allow keyboard `d` to return to daily rotation.
5. Decode the top-loop frame into the 400 px top circle.
6. Apply a subtle live ambiance/twinkle overlay inside the circular cutouts.
7. Draw dial markings and real-time hands over the top circle.
8. Draw the themed pendulum over a 300 px lower design backdrop.

The fixed geometry is currently:

- screen: 480x800;
- top cutout: 400 px diameter, calibrated at x=224, y=260;
- bottom cutout: 300 px diameter, calibrated at x=210, y=650;
- fixture ring: 18 px black stroke.

Those values match the current fixture direction and should become the first
things to tune when the printed bezel dimensions are final.

## 7. Raspberry Pi Integration

The renderer should run before networking:

- systemd renderer service starts after local filesystems, not
  `network-online.target`;
- RTC provides correct time without Wi-Fi;
- Wi-Fi provisioning is handled by Comitup SoftAP/captive portal and does not
  block the renderer. A four-second dial hold opens recovery; its root helper
  exposes only status, scan, and confirmed hotspot-reset actions;
- NTP, when available, writes corrected time back to the DS3231.

The installer defaults the renderer service user to the sudo/login user because
that matches the display ownership path proven on the current Pi. It can still
be overridden with `PICLOCK_USER=piclock` for a dedicated service account, but
that path must be validated on-device for DRM master/input permissions.

## 8. Remaining Validation Risk

These items are written or configured but require the physical Pi:

- DRM/KMS startup on tty1 after a cold boot;
- DSI panel rotation and separate touch rotation;
- Comitup captive portal and long-press recovery while the renderer is active;
- DS3231 overlay/hwclock behavior after power loss;
- real CPU/RAM usage after several hours of looping.

## 9. Recommendation

Stay with the native renderer. It is the better long-term structure for this
appliance and it keeps the Klydo-style split between authored media and live
time. The legacy HTML remains useful as a visual reference, but the production
path should be design folders plus a small native boot service.
