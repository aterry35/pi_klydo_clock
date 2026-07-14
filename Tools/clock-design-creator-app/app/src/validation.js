import { slugify } from './utils.js';
import {
  CIRCLE_DIAMETERS, DIAL_SIZE, PENDULUM_SIZE, VIDEO_LIMITS,
} from './clockConfig.js';

const HEX_COLOR = /^#[0-9a-f]{6}$/i;
const HAND_SHAPES = new Set(['rounded', 'spindle']);
const MARKINGS = new Set(['none', 'ticks', 'numerals', 'both']);
const BACKDROPS = new Set(['loop', 'solid', 'none']);

function result(level, code, message) {
  return { level, code, message };
}

function finiteInRange(value, min, max) {
  return Number.isFinite(value) && value >= min && value <= max;
}

export function validateTheme(theme) {
  const checks = [];
  const error = (code, message) => checks.push(result('error', code, message));

  if (!HEX_COLOR.test(theme.accent)) error('theme.accent', 'Accent must be a six-digit hex colour.');
  if (!HEX_COLOR.test(theme.background)) error('theme.background', 'Background must be a six-digit hex colour.');

  for (const key of ['hour', 'minute', 'second']) {
    const hand = theme.hands?.[key];
    if (!hand) {
      error(`hands.${key}`, `Missing ${key} hand settings.`);
      continue;
    }
    if (!HEX_COLOR.test(hand.color)) error(`hands.${key}.color`, `${key} hand colour is invalid.`);
    if (!finiteInRange(hand.width, 1, 30)) error(`hands.${key}.width`, `${key} hand width is outside 1-30.`);
    if (!finiteInRange(hand.length, 0.1, 1)) error(`hands.${key}.length`, `${key} hand length is outside 0.1-1.`);
    if (key !== 'second' && !HAND_SHAPES.has(hand.shape)) error(`hands.${key}.shape`, `${key} hand shape is invalid.`);
  }

  if (!MARKINGS.has(theme.dial?.markings)) error('dial.markings', 'Dial markings mode is invalid.');
  if (!finiteInRange(theme.dial?.count, 1, 60)) error('dial.count', 'Dial marking count is outside 1-60.');
  if (!HEX_COLOR.test(theme.dial?.color)) error('dial.color', 'Dial marking colour is invalid.');
  if (!finiteInRange(theme.dial?.diameter, CIRCLE_DIAMETERS.dial.min, CIRCLE_DIAMETERS.dial.max)) {
    error('dial.diameter', `Dial diameter is outside ${CIRCLE_DIAMETERS.dial.min}-${CIRCLE_DIAMETERS.dial.max} pixels.`);
  }

  const pendulum = theme.pendulum;
  if (!finiteInRange(pendulum?.period_s, 0.2, 10)) error('pendulum.period_s', 'Pendulum period is outside 0.2-10 seconds.');
  if (!finiteInRange(pendulum?.amplitude_deg, 0, 30)) error('pendulum.amplitude_deg', 'Pendulum amplitude is outside 0-30 degrees.');
  if (!finiteInRange(pendulum?.pivot_x, 0, 1) || !finiteInRange(pendulum?.pivot_y, 0, 1)) {
    error('pendulum.pivot', 'Pendulum pivot must be inside the lower cutout.');
  }

  if (!BACKDROPS.has(theme.bottom?.backdrop)) error('bottom.backdrop', 'Bottom backdrop is invalid.');
  if (!HEX_COLOR.test(theme.bottom?.color)) error('bottom.color', 'Bottom colour is invalid.');
  if (!finiteInRange(theme.bottom?.diameter, CIRCLE_DIAMETERS.pendulum.min, CIRCLE_DIAMETERS.pendulum.max)) {
    error('bottom.diameter', `Pendulum background diameter is outside ${CIRCLE_DIAMETERS.pendulum.min}-${CIRCLE_DIAMETERS.pendulum.max} pixels.`);
  }
  return checks;
}

export function validateProject(state, resources = {}, capabilities = {}) {
  const checks = [];
  const add = (level, code, message) => checks.push(result(level, code, message));
  const slug = slugify(state.name);

  if (!state.name.trim() || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) {
    add('error', 'slug', 'Enter a name that produces a filesystem-safe slug.');
  } else {
    add('ok', 'slug', `Slug "${slug}" is filesystem-safe.`);
  }

  if (state.dial.mode === 'media' && !resources.dialMedia) {
    add('error', 'dial-media', 'Import media mode is selected but no decoded image or video is loaded.');
  } else {
    add('ok', 'dial-size', `Dial output is exactly ${DIAL_SIZE} x ${DIAL_SIZE}.`);
  }

  if (state.dial.mediaKind === 'video' && state.dial.mediaDuration) {
    const difference = Math.abs(state.dial.duration - state.dial.mediaDuration);
    if (difference > 0.08) {
      add('error', 'video-loop-duration', 'Loop duration must match the imported video duration for a clean seam.');
    }
  }

  const [preferredMin, preferredMax] = VIDEO_LIMITS.preferredDuration;
  if (state.dial.duration >= preferredMin && state.dial.duration <= preferredMax) {
    add('ok', 'duration', `Loop duration is ${state.dial.duration} seconds.`);
  } else {
    add('warning', 'duration', `A ${preferredMin}-${preferredMax} second loop is recommended for the Pi.`);
  }

  if (state.dial.fps === VIDEO_LIMITS.preferredFps) {
    add('ok', 'fps', `Frame rate is ${VIDEO_LIMITS.preferredFps} fps.`);
  } else {
    add('warning', 'fps', `${state.dial.fps} fps selected; ${VIDEO_LIMITS.preferredFps} fps is recommended for the Pi.`);
  }

  if (state.pendulum.mode === 'image' && !resources.pendulumImage) {
    add('error', 'pendulum-image', 'Import PNG mode is selected but no decoded image is loaded.');
  } else if (state.pendulum.mode === 'image' && !state.pendulum.imageHasAlpha) {
    add('warning', 'pendulum-alpha', 'The imported pendulum has no transparent pixels.');
  } else if (state.pendulum.mode === 'builder' && !finiteInRange(
    state.pendulum.bobSize,
    20,
    (PENDULUM_SIZE.width - 40) / 2,
  )) {
    add('error', 'pendulum-bob-width', `Pendulum bob width must be between 40 and ${PENDULUM_SIZE.width - 40} pixels.`);
  } else {
    add('ok', 'pendulum', `Pendulum output is a transparent ${PENDULUM_SIZE.width} x ${PENDULUM_SIZE.height} PNG.`);
  }

  const themeErrors = validateTheme(state.theme);
  if (themeErrors.length) checks.push(...themeErrors);
  else add('ok', 'theme', 'theme.json matches the renderer schema.');

  if (!capabilities.webCodecs) {
    add('error', 'webcodecs', 'This browser cannot create deterministic H.264 video. Use current Chrome or Edge.');
  } else {
    add('ok', 'webcodecs', 'Deterministic H.264 encoding is available.');
  }

  return checks;
}

export function summarizeValidation(checks) {
  return {
    errors: checks.filter((check) => check.level === 'error').length,
    warnings: checks.filter((check) => check.level === 'warning').length,
  };
}

export function validateEncodedVideo(metadata) {
  const expectedFrames = Math.round(metadata.duration * metadata.fps);
  const errors = [];
  if (metadata.width !== DIAL_SIZE || metadata.height !== DIAL_SIZE) {
    errors.push(`Encoded video is not ${DIAL_SIZE} x ${DIAL_SIZE}.`);
  }
  if (metadata.codec !== 'avc1.42001f') errors.push('Encoded video is not H.264 Constrained Baseline.');
  if (metadata.frameCount !== expectedFrames) {
    errors.push(`Encoded ${metadata.frameCount} frames; expected ${expectedFrames}.`);
  }
  if (metadata.byteLength < 1024) errors.push('Encoded MP4 is unexpectedly small.');
  return errors;
}
