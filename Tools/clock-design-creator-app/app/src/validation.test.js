import { describe, expect, it } from 'vitest';
import { createInitialState } from './defaults.js';
import { validateEncodedVideo, validateProject } from './validation.js';

describe('project validation', () => {
  it('accepts the built-in project when H.264 is available', () => {
    const state = createInitialState();
    const checks = validateProject(state, {}, { webCodecs: true });
    expect(checks.filter((check) => check.level === 'error')).toEqual([]);
  });

  it('rejects media mode without decoded media', () => {
    const state = createInitialState();
    state.dial.mode = 'media';
    const checks = validateProject(state, {}, { webCodecs: true });
    expect(checks.some((check) => check.code === 'dial-media' && check.level === 'error')).toBe(true);
  });

  it('rejects a video duration that would cut the source loop', () => {
    const state = createInitialState();
    state.dial.mode = 'media';
    state.dial.mediaKind = 'video';
    state.dial.mediaDuration = 5;
    state.dial.duration = 6;
    const checks = validateProject(state, { dialMedia: {} }, { webCodecs: true });
    expect(checks.some((check) => check.code === 'video-loop-duration' && check.level === 'error')).toBe(true);
  });

  it('accepts a pendulum bob wider than 70 pixels', () => {
    const state = createInitialState();
    state.pendulum.bobSize = 60;
    const checks = validateProject(state, {}, { webCodecs: true });
    expect(checks.some((check) => check.code === 'pendulum-bob-width')).toBe(false);
  });

  it('accepts adjustable dial and pendulum background diameters', () => {
    const state = createInitialState();
    state.theme.dial.diameter = 500;
    state.theme.bottom.diameter = 340;
    const checks = validateProject(state, {}, { webCodecs: true });
    expect(checks.some((check) => check.code === 'dial.diameter')).toBe(false);
    expect(checks.some((check) => check.code === 'bottom.diameter')).toBe(false);
  });

  it('rejects background diameters outside the renderer limits', () => {
    const state = createInitialState();
    state.theme.dial.diameter = 502;
    state.theme.bottom.diameter = 400;
    const checks = validateProject(state, {}, { webCodecs: true });
    expect(checks.some((check) => check.code === 'dial.diameter' && check.level === 'error')).toBe(true);
    expect(checks.some((check) => check.code === 'bottom.diameter' && check.level === 'error')).toBe(true);
  });
});

describe('encoded video validation', () => {
  it('requires the exact requested frame count', () => {
    expect(validateEncodedVideo({
      codec: 'avc1.42001f', width: 480, height: 480, duration: 6,
      fps: 15, frameCount: 5, byteLength: 20_000,
    })).toContain('Encoded 5 frames; expected 90.');
  });

  it('accepts exact H.264 metadata', () => {
    expect(validateEncodedVideo({
      codec: 'avc1.42001f', width: 480, height: 480, duration: 6,
      fps: 15, frameCount: 90, byteLength: 200_000,
    })).toEqual([]);
  });
});
