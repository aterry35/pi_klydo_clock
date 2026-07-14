# Prompt For Claude Design: Pi Clock Design Creator App

Use this prompt with Claude Design or another app-building assistant.

```text
Create a polished web app called "Pi Clock Design Creator" for artists and non-technical users to create exportable design packages for a Raspberry Pi art clock.

The app must create designs for this exact target format:

<design-slug>/
  loop.mp4
  pendulum.png
  theme.json

The clock display has:
- a 480 x 800 portrait canvas;
- a top circular dial cutout centered at x=240, y=250, radius=200;
- a lower circular pendulum cutout centered at x=240, y=640, radius=150;
- real-time clock hands are rendered by the Raspberry Pi app, not baked into the dial animation unless the user intentionally chooses that.

Core product goal:
Let a user create a dial animation and pendulum face, preview it in the real 480x800 clock layout, configure the theme JSON, validate the package, and export a zip file that can be copied to the Pi.

Required app features:

1. Project setup
- User enters design name.
- App generates a filesystem-safe slug such as "sunny-kitchen".
- User can choose a template: blank, paper-cut mandala, vintage film, geometric, color waves, photo/video import.

2. Dial animation editor
- Dial artwork is exactly 480 x 480.
- User can import an image or short video.
- User can crop/scale to a square.
- User can create simple procedural animations such as rotating layers, breathing scale, drifting shapes, waves, film grain, or color cycling.
- User can preview a seamless loop.
- Export must produce loop.mp4 at 480x480, preferably H.264, 15 fps, 4-10 seconds, no audio.

3. Pendulum editor
- Pendulum artwork target is 300 x 400 transparent PNG.
- The pivot must be at the top center of the image.
- Show a pivot guide line and lower circular cutout guide.
- User can design a bob/rod using shapes, colors, imported images, or SVG-like controls.
- Export must produce pendulum.png with transparency.

4. Clock theme editor
- Let the user configure:
  - hour hand color, width, length, shape;
  - minute hand color, width, length, shape;
  - second hand visible/hidden, color, width, length;
  - accent color;
  - background color;
  - dial markings: none, ticks, numerals, both;
  - pendulum period_s;
  - pendulum amplitude_deg;
  - pendulum pivot;
  - bottom backdrop: loop, solid, none;
  - bottom color when solid;
  - ambiance day_night, twinkle, glow.
- Generate theme.json exactly in this schema:

{
  "name": "Sunny Kitchen",
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
    "backdrop": "solid",
    "color": "#000000"
  },
  "ambiance": {
    "day_night": false,
    "twinkle": false,
    "glow": false
  }
}

5. Live preview
- Show the full 480x800 clock layout.
- Top circle displays the dial animation.
- Draw the real-time hour/minute/optional second hands over the animation.
- Lower circle displays the selected bottom backdrop and the pendulum image swinging.
- Provide play/pause and time scrub controls.
- Preview should match the Raspberry Pi app geometry.

6. Validation
- Before export, validate:
  - design slug is filesystem safe;
  - loop animation exists and is 480x480;
  - pendulum image exists and has transparency;
  - theme.json is valid;
  - video length is 4-10 seconds preferred;
  - fps is 15 preferred;
  - no missing required files.
- Show clear errors and warnings.

7. Export
- Export a zip named <design-slug>.zip.
- The zip must contain one top-level folder named <design-slug>.
- The folder must contain:
  - loop.mp4
  - pendulum.png
  - theme.json
  - preview.png optional
  - README.txt optional
- Include copy instructions after export:
  - SD card path: piclock-designs/<design-slug>/
  - SCP path: scp -r <design-slug> terry@192.168.1.217:/home/terry/piclock-designs/

UI design requirements:
- Make the first screen the actual editor, not a marketing page.
- Use a professional creative-tool layout with a left tool panel, center preview canvas, and right inspector.
- Use compact controls, icons, color swatches, sliders, toggles, and tabs.
- Include templates and sensible defaults so a user can export a working design quickly.
- Keep all text inside controls readable on laptop-sized screens.

Implementation preference:
- Build as a browser app using React or a similar framework.
- Use HTML canvas or WebGL for preview.
- Use ffmpeg.wasm or a backend export service if needed to create MP4 files.
- If MP4 export is too heavy in the browser, export image frames plus a clear server-side conversion command, but the final product should aim to export loop.mp4 directly.

Do not create a landing page. Build the editor experience directly.
```
