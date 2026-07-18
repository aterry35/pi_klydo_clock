import clockSettings from '../../../../config/clock.json';

const { display, layout, enclosure, designs } = clockSettings;
const previewLayout = clockSettings.designer?.preview;
const dialCenter = previewLayout?.dial_center ?? layout.dial.center;
const pendulumCenter = previewLayout?.pendulum_center ?? layout.pendulum.center;

export const FIXTURE = Object.freeze({
  widthMm: enclosure.panel_mm[0],
  heightMm: enclosure.panel_mm[1],
  dial: Object.freeze({
    leftMm: enclosure.dial_aperture.left_mm,
    topMm: enclosure.dial_aperture.top_mm,
    diameterMm: enclosure.dial_aperture.diameter_mm,
  }),
  pendulum: Object.freeze({
    leftMm: enclosure.pendulum_aperture.left_mm,
    topMm: enclosure.pendulum_aperture.top_mm,
    diameterMm: enclosure.pendulum_aperture.diameter_mm,
  }),
});

export const CLOCK = Object.freeze({
  width: display.width,
  height: display.height,
  fixtureBorder: layout.fixture_border_px,
  top: Object.freeze({
    cx: dialCenter[0],
    cy: dialCenter[1],
    r: layout.dial.default_diameter / 2,
  }),
  bottom: Object.freeze({
    cx: pendulumCenter[0],
    cy: pendulumCenter[1],
    r: layout.pendulum.default_diameter / 2,
  }),
});

export const CIRCLE_DIAMETERS = Object.freeze({
  dial: Object.freeze({
    min: layout.dial.minimum_diameter,
    max: layout.dial.maximum_diameter,
    default: layout.dial.default_diameter,
  }),
  pendulum: Object.freeze({
    min: layout.pendulum.minimum_diameter,
    max: layout.pendulum.maximum_diameter,
    default: layout.pendulum.default_diameter,
  }),
});

export const DIAL_SIZE = designs.assets.dial_canvas[0];
export const PENDULUM_SIZE = Object.freeze({
  width: designs.assets.pendulum_canvas[0],
  height: designs.assets.pendulum_canvas[1],
});

export const VIDEO_LIMITS = Object.freeze({
  minFps: designs.assets.video_min_fps,
  preferredFps: designs.assets.video_preferred_fps,
  maxFps: designs.assets.video_max_fps,
  minDuration: designs.assets.video_min_duration_s,
  preferredDuration: Object.freeze(designs.assets.video_preferred_duration_s),
  maxDuration: designs.assets.video_max_duration_s,
});
