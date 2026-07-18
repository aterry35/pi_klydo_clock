# Pi Clock Design Creator

The production React/Vite source is in `app/`.

## Run The Editor

```bash
cd Tools/clock-design-creator-app/app
npm install
npm run dev
```

Open the local URL printed by Vite. Editing and local ZIP export do not require an
account, and imported media stays in the browser until the user publishes. Publishing
uploads the validated package and preview to the Community gallery.

The editor requires a current Chromium browser with WebCodecs H.264 support.
Chrome and Edge are the supported export browsers.

The built-in starting points include dedicated Kitchen Pop and Paper Cut
generators. Both are fully procedural, so their animation, palette, hands,
pendulum proportions, and circle sizes remain editable before export.

The preview uses the production enclosure registration: a 76 mm dial opening and
48.5 mm pendulum opening on the 102 x 165 mm printed face. Background-size controls
retain overscan so the recessed display does not expose a black edge through either
opening.

The editor imports the repository's `config/clock.json` directly. Preview centers,
circle diameter limits, CAD measurements, output canvas sizes, frame-rate limits,
and duration limits therefore stay synchronized with the native renderer. Restart
Vite after changing that file if hot reload does not pick up an external JSON edit.

## Community publishing

The Community page is publicly readable. Registering an artist account enables
publishing, likes, and comments. The artist name is written into `theme.json`, shown
on gallery cards, and must match the signed-in profile when publishing. Community
submissions require an enabled dial watermark; the Pi renderer draws it over the
upper dial without baking it into the loop video.

Published packages become visible immediately. Signed-in users can report a design,
and administrators have a private dashboard for hide/restore, account suspension,
report resolution, and audit review. Email verification, password reset, and
pre-publication approval are not part of the soft opening.

## Build And Test

```bash
npm test
npm run build
```

The production build is written to `app/dist/` and contains local JavaScript and
CSS assets. It does not depend on Google Fonts or a React CDN.

## Export Contract

Every ZIP contains one top-level design folder:

```text
<design-slug>/
  loop.mp4
  pendulum.png
  theme.json
  preview.png
  export-report.json
  README.txt
```

`loop.mp4` is encoded deterministically as 480x480 H.264. The exporter renders
exactly `duration * fps` frames and refuses to package the result if the encoded
frame count does not match.

Validate an extracted design with the project validator:

```bash
python scripts/validate_design.py /path/to/<design-slug>
```

The validator decodes the video and checks resolution, codec, frame rate,
duration, and minimum decoded frame count.
